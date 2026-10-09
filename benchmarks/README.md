# OfflineScribeAI Benchmarks

Use the package benchmark harness from the repository root:

```bash
offlinescribe make-sample work/sample.wav
python -m offlinescribe.benchmark work/sample.wav \
  --reference benchmarks/reference_transcript.txt \
  --out work/benchmark.json
```

The harness measures transcription elapsed time, real-time factor, word error rate, Python peak RAM allocation, optional CUDA peak VRAM, SOAP structuring latency, and extracted entity count. All transcription and note structuring work runs inside `NetworkSandbox`.

