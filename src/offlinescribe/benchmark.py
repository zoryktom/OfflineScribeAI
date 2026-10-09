"""Benchmark harness for OfflineScribeAI."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import time
import tracemalloc
from pathlib import Path
from typing import Any

from offlinescribe.audio.transcriber import TranscriptionConfig, transcriber_from_config
from offlinescribe.nlp.entities import extract_clinical_entities
from offlinescribe.nlp.soap import parse_soap
from offlinescribe.privacy import NetworkSandbox


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OfflineScribeAI benchmark harness.")
    parser.add_argument("audio_path")
    parser.add_argument("--reference", help="Reference transcript for WER.")
    parser.add_argument("--out", help="Write JSON metrics to this path.")
    parser.add_argument("--backend", choices=["auto", "metadata", "faster-whisper"], default="auto")
    parser.add_argument("--model-path")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--chunk-seconds", type=float, default=15.0)
    parser.add_argument("--language", default="en")
    args = parser.parse_args(argv)

    config = TranscriptionConfig(
        backend=args.backend,
        model_path=args.model_path,
        compute_type=args.compute_type,
        device=args.device,
        chunk_seconds=args.chunk_seconds,
        language=args.language,
    )
    metrics = run_benchmark(Path(args.audio_path), config=config, reference_path=args.reference)
    payload = json.dumps(metrics, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


def run_benchmark(
    audio_path: Path,
    config: TranscriptionConfig | None = None,
    reference_path: str | Path | None = None,
) -> dict[str, Any]:
    cfg = config or TranscriptionConfig()
    tracemalloc.start()
    reset_cuda_peak_memory()

    with NetworkSandbox("benchmark transcription"):
        transcriber = transcriber_from_config(cfg)
        transcription_start = time.perf_counter()
        transcription = transcriber.transcribe(audio_path)
        transcription_seconds = time.perf_counter() - transcription_start

    note_start = time.perf_counter()
    with NetworkSandbox("benchmark SOAP structuring"):
        soap = parse_soap(transcription.text)
        entities = extract_clinical_entities(transcription.text, soap.section_spans)
    note_latency_seconds = time.perf_counter() - note_start

    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    reference = Path(reference_path).read_text(encoding="utf-8") if reference_path else ""
    metrics = {
        "audio_path": str(audio_path),
        "backend": transcription.backend,
        "duration_seconds": transcription.duration_seconds,
        "transcription_seconds": transcription_seconds,
        "rtf": _safe_divide(transcription_seconds, transcription.duration_seconds),
        "wer": word_error_rate(reference, transcription.text) if reference else None,
        "peak_ram_mb": round(peak_bytes / (1024 * 1024), 4),
        "current_ram_mb": round(current_bytes / (1024 * 1024), 4),
        "platform_max_rss_mb": _max_rss_mb(),
        "peak_vram_mb": peak_cuda_memory_mb(),
        "note_latency_seconds": note_latency_seconds,
        "entity_count": len(entities),
        "soap_nonempty_sections": [key for key, value in soap.as_dict().items() if value],
    }
    return metrics


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref_words = _words(reference)
    hyp_words = _words(hypothesis)
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    previous = list(range(len(hyp_words) + 1))
    for i, ref_word in enumerate(ref_words, start=1):
        current = [i]
        for j, hyp_word in enumerate(hyp_words, start=1):
            substitution_cost = 0 if ref_word == hyp_word else 1
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1] / len(ref_words)


def reset_cuda_peak_memory() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        return


def peak_cuda_memory_mb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / (1024 * 1024), 4)
    except Exception:
        return None
    return None


def _words(text: str) -> list[str]:
    return [word.strip(".,;:!?()[]{}\"'").lower() for word in text.split() if word.strip(".,;:!?()[]{}\"'")]


def _safe_divide(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _max_rss_mb() -> float | None:
    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return None
    if platform.system() == "Darwin":
        return round(rss / (1024 * 1024), 4)
    return round(rss / 1024, 4)


if __name__ == "__main__":
    raise SystemExit(main())

