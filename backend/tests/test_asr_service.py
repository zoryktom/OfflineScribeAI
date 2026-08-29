import subprocess
from pathlib import Path

import pytest

from app.asr_service import (
    AsrError,
    load_whisper_model,
    prepare_audio_for_asr,
    transcribe_audio,
    validate_audio_upload,
)
from app.models import TranscriptResult

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEECH_SAMPLE = _REPO_ROOT / "audio_samples" / "english_speech_sample.wav"


def test_validate_rejects_non_audio_extension():
    with pytest.raises(AsrError, match="not a supported audio format"):
        validate_audio_upload(filename="notes.txt", content_type="text/plain")


def test_validate_rejects_wrong_mime_on_wav_name():
    with pytest.raises(AsrError, match="not recognized as audio"):
        validate_audio_upload(filename="visit.wav", content_type="text/plain")


def test_validate_accepts_webm():
    suffix = validate_audio_upload(filename="visit.webm", content_type="audio/webm")
    assert suffix == ".webm"


def test_prepare_wav_skips_ffmpeg(tmp_path, monkeypatch):
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF")

    def fail_which(_name: str) -> None:
        raise AssertionError("ffmpeg should not be required for WAV")

    monkeypatch.setattr("app.asr_service.shutil.which", fail_which)
    assert prepare_audio_for_asr(wav) == wav


def test_prepare_webm_converts_with_ffmpeg(tmp_path, monkeypatch):
    webm = tmp_path / "clip.webm"
    webm.write_bytes(b"fake-webm-bytes")
    converted: list[Path] = []

    monkeypatch.setattr("app.asr_service.shutil.which", lambda _name: "/usr/bin/ffmpeg")

    def fake_run(cmd, **_kwargs):
        dest = Path(cmd[-1])
        dest.write_bytes(b"RIFF")
        converted.append(dest)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr("app.asr_service.subprocess.run", fake_run)

    out = prepare_audio_for_asr(webm)
    try:
        assert out != webm
        assert out.suffix == ".wav"
        assert converted == [out]
        assert out.read_bytes().startswith(b"RIFF")
    finally:
        out.unlink(missing_ok=True)


def test_prepare_webm_without_ffmpeg_is_actionable(tmp_path, monkeypatch):
    webm = tmp_path / "clip.webm"
    webm.write_bytes(b"fake-webm-bytes")
    monkeypatch.setattr("app.asr_service.shutil.which", lambda _name: None)

    with pytest.raises(AsrError, match="brew install ffmpeg"):
        prepare_audio_for_asr(webm)


def test_transcribe_audio_missing_file_raises():
    with pytest.raises(AsrError, match="not found"):
        transcribe_audio("/no/such/recording.wav")


def test_transcribe_real_speech_sample_returns_segments():
    assert _SPEECH_SAMPLE.is_file(), (
        "audio_samples/english_speech_sample.wav is missing. "
        "Add a few seconds of clear English speech for this test."
    )
    load_whisper_model()
    result = transcribe_audio(_SPEECH_SAMPLE)

    assert isinstance(result, TranscriptResult)
    assert result.text.strip()
    assert result.segments
    for segment in result.segments:
        assert segment.end_s >= segment.start_s
        assert segment.text.strip()
        assert segment.speaker == "unknown"
    joined = " ".join(segment.text for segment in result.segments)
    assert joined.replace("  ", " ").strip() == result.text.strip()
