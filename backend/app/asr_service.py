"""On-device transcription with faster-whisper.

The Whisper model is loaded once at API startup and reused. This module does
not send audio off the clinic computer after the first model download.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.asr_flags import flag_asr_concerns
from app.models import SpeakerTurn, TranscriptResult

logger = logging.getLogger(__name__)

_model: Any | None = None
_model_lock = threading.Lock()

# WAV is passed straight to faster-whisper. Browser recordings are usually webm
# (sometimes mp4 on Safari) and are converted with ffmpeg first.
_WAV_SUFFIXES = {".wav"}
_ALLOWED_SUFFIXES = {
    ".wav",
    ".webm",
    ".mp3",
    ".m4a",
    ".ogg",
    ".oga",
    ".flac",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".aac",
}
_ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/webm",
    "video/webm",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
    "audio/x-flac",
    "video/mp4",
    "application/octet-stream",
}

_FFMPEG_MISSING = (
    "ffmpeg is not installed on this computer, so browser recordings "
    "(WebM or MP4) cannot be converted for transcription. "
    "On macOS install it with: brew install ffmpeg. "
    "On Debian or Ubuntu: sudo apt install ffmpeg. "
    "Then restart the local API."
)


class AsrError(Exception):
    """Raised when audio cannot be transcribed. Message is safe to show a clinician."""


def load_whisper_model() -> Any:
    """Load faster-whisper once and keep it in memory. Safe to call repeatedly."""
    global _model
    with _model_lock:
        if _model is not None:
            return _model

        settings = get_settings()
        device = settings.asr_device.strip().lower()
        if device not in {"cpu", "cuda"}:
            raise AsrError(
                "ASR_DEVICE must be cpu or cuda. The default is cpu for laptops without a GPU."
            )

        models_dir = settings.whisper_models_dir
        models_dir.mkdir(parents=True, exist_ok=True)
        use_local_only = _has_local_whisper_cache(models_dir, settings.asr_model_size)
        logger.info(
            "asr loading model_size=%s device=%s local_cache=%s",
            settings.asr_model_size,
            device,
            use_local_only,
        )
        try:
            from faster_whisper import WhisperModel

            try:
                _model = WhisperModel(
                    settings.asr_model_size,
                    device=device,
                    compute_type=settings.whisper_compute_type,
                    download_root=str(models_dir),
                    local_files_only=use_local_only,
                )
            except Exception:
                if not use_local_only:
                    raise
                logger.info("asr local cache incomplete; downloading model files")
                _model = WhisperModel(
                    settings.asr_model_size,
                    device=device,
                    compute_type=settings.whisper_compute_type,
                    download_root=str(models_dir),
                    local_files_only=False,
                )
        except AsrError:
            raise
        except Exception as exc:
            logger.exception("asr model load failed")
            raise AsrError(
                "Could not load the speech model on this computer. "
                "The first run downloads model files — check disk space and internet, "
                "then restart the local API. After that, transcription stays offline."
            ) from exc
        return _model


def reset_whisper_model() -> None:
    """Drop the cached model. Used by tests only."""
    global _model
    with _model_lock:
        _model = None


def validate_audio_upload(*, filename: str | None, content_type: str | None) -> str:
    """Return the normalized suffix, or raise AsrError for unrecognized audio."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise AsrError(
            f"That file type ({suffix or 'unknown'}) is not a supported audio format. "
            "Upload a .wav, .webm, .mp3, .m4a, .ogg, or .flac recording."
        )
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime and mime not in _ALLOWED_MIME_TYPES and not mime.startswith("audio/"):
        raise AsrError(
            "That upload is not recognized as audio. "
            "Upload a .wav, .webm, .mp3, .m4a, .ogg, or .flac recording."
        )
    return suffix


def prepare_audio_for_asr(source: Path) -> Path:
    """Return a path faster-whisper can decode. Converts non-WAV via ffmpeg.

    WAV inputs are returned unchanged. Any other allowed format is converted to
    a 16 kHz mono PCM WAV temp file. The caller must delete that temp file.
    """
    if not source.is_file():
        raise AsrError(
            f"Audio file not found at {source}. Choose a recording and try again."
        )
    if source.suffix.lower() in _WAV_SUFFIXES:
        return source

    ffmpeg = _require_ffmpeg()
    fd, dest_name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    dest = Path(dest_name)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        dest.unlink(missing_ok=True)
        raise AsrError(
            "Converting that recording to WAV took too long. Try a shorter file."
        ) from exc
    except subprocess.CalledProcessError as exc:
        dest.unlink(missing_ok=True)
        logger.error("ffmpeg conversion failed exit_code=%s", exc.returncode)
        raise AsrError(
            "Could not convert that recording to WAV. "
            "Try exporting the visit as a .wav file and upload it again."
        ) from exc
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise AsrError(
            "Could not run ffmpeg to convert that recording. "
            "Confirm ffmpeg is installed, then restart the local API."
        ) from exc
    return dest


def transcribe_audio(audio_path: str | Path) -> TranscriptResult:
    """Transcribe an audio file. Returns full text plus timestamped segments."""
    path = Path(audio_path)
    if not path.is_file():
        raise AsrError(
            f"Audio file not found at {path}. Choose a recording and try again."
        )

    model = load_whisper_model()
    settings = get_settings()
    try:
        raw_segments, info = model.transcribe(
            str(path),
            language=settings.language,
            word_timestamps=True,
        )
        segments: list[SpeakerTurn] = []
        parts: list[str] = []
        words: list[tuple[str, float, float, float | None]] = []
        for raw in raw_segments:
            text = (raw.text or "").strip()
            if not text:
                continue
            parts.append(text)
            segments.append(
                SpeakerTurn(
                    # TODO: real speaker diarization — faster-whisper has no
                    # speaker labels. Keep timestamps so diarization can fill
                    # this field later without a storage rewrite.
                    speaker="unknown",
                    start_s=float(raw.start),
                    end_s=float(raw.end),
                    text=text,
                )
            )
            for word in getattr(raw, "words", None) or []:
                token = (getattr(word, "word", "") or "").strip()
                if not token:
                    continue
                probability = getattr(word, "probability", None)
                words.append(
                    (
                        token,
                        float(getattr(word, "start", raw.start)),
                        float(getattr(word, "end", raw.end)),
                        float(probability) if probability is not None else None,
                    )
                )
    except AsrError:
        raise
    except Exception as exc:
        logger.exception("asr decode failed")
        raise AsrError(
            "The speech model could not read that recording. "
            "Try a .wav file, or confirm ffmpeg is installed for browser recordings."
        ) from exc

    full_text = " ".join(parts).strip()
    if not full_text:
        raise AsrError(
            "No speech was detected in that recording. "
            "Try a clearer microphone recording and try again."
        )

    language = getattr(info, "language", None) or settings.language
    asr_flags = flag_asr_concerns(segments, words=words or None)
    if asr_flags:
        logger.info("asr review_flags=%s", len(asr_flags))
    return TranscriptResult(
        text=full_text,
        language=language,
        segments=segments,
        asr_flags=asr_flags,
    )


def _require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise AsrError(_FFMPEG_MISSING)
    return path


def _has_local_whisper_cache(models_dir: Path, model_size: str) -> bool:
    """True when a previous download of this model id is already on disk."""
    marker = model_size.replace("/", "--")
    if not models_dir.is_dir():
        return False
    for cached in models_dir.glob("models--*"):
        snapshots = cached / "snapshots"
        if marker in cached.name and snapshots.is_dir() and any(snapshots.iterdir()):
            return True
    return False
