import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from offlinescribe.audio.buffer import AudioStreamBuffer, WavChunkReader
from offlinescribe.audio.synthetic import DEFAULT_SYNTHETIC_TRANSCRIPT, write_synthetic_wav
from offlinescribe.audio.transcriber import MetadataTranscriber


class AudioPipelineTests(unittest.TestCase):
    def test_wav_chunk_reader_and_metadata_transcriber(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = write_synthetic_wav(Path(temp_dir) / "sample.wav", duration_seconds=1.0)

            chunks = list(WavChunkReader(wav_path, chunk_seconds=0.25))
            self.assertEqual(len(chunks), 4)
            self.assertEqual(chunks[0].start_seconds, 0.0)
            self.assertEqual(chunks[-1].end_seconds, 1.0)

            result = MetadataTranscriber(chunk_seconds=0.25).transcribe(wav_path)
            self.assertEqual(result.text, DEFAULT_SYNTHETIC_TRANSCRIPT)
            self.assertEqual(result.backend, "metadata")
            self.assertEqual(result.segments[0].speaker, "patient")
            self.assertEqual(result.segments[1].speaker, "clinician")

    def test_audio_stream_buffer_emits_bounded_chunks(self):
        buffer = AudioStreamBuffer(sample_rate=10, channels=1, sample_width=2, chunk_seconds=0.5, max_buffer_seconds=1.0)
        pcm = b"\x00\x00" * 5

        chunks = buffer.append_pcm(pcm)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].start_seconds, 0.0)
        self.assertEqual(chunks[0].end_seconds, 0.5)
        self.assertIsNone(buffer.flush())

    def test_cli_transcribe_synthetic_wav_to_soap_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = write_synthetic_wav(Path(temp_dir) / "sample.wav")
            out_path = Path(temp_dir) / "note.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "offlinescribe",
                    "transcribe",
                    str(wav_path),
                    "--format",
                    "soap",
                    "--out",
                    str(out_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(completed.stderr, "")
            note = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIs(note["audit"]["offline_enforced"], True)
            self.assertEqual(note["audit"]["network_attempts"], [])
            self.assertTrue(note["soap"]["subjective"])
            self.assertTrue(note["soap"]["objective"])
            self.assertTrue(note["soap"]["plan"])
            self.assertTrue(any(entity["vocabulary"] == "RxNorm" for entity in note["entities"]))


if __name__ == "__main__":
    unittest.main()
