import tempfile
import unittest
from pathlib import Path

from offlinescribe.audio.synthetic import write_synthetic_wav
from offlinescribe.audio.transcriber import TranscriptionConfig
from offlinescribe.nlp.entities import extract_clinical_entities
from offlinescribe.nlp.soap import parse_soap
from offlinescribe.ambient import process_audio_to_note
from offlinescribe.schema import validate_note_schema


class SoapSchemaTests(unittest.TestCase):
    def test_parse_explicit_soap_sections_and_entities(self):
        transcript = (
            "Subjective: Patient reports cough and fever. "
            "Objective: Temperature 101 F and oxygen saturation 96 percent. "
            "Assessment: Upper respiratory infection with asthma. "
            "Plan: Use albuterol and acetaminophen."
        )

        soap = parse_soap(transcript)
        entities = extract_clinical_entities(transcript, soap.section_spans)

        self.assertEqual(soap.subjective, "Patient reports cough and fever")
        self.assertTrue(soap.objective.startswith("Temperature"))
        self.assertTrue(soap.assessment.startswith("Upper respiratory infection"))
        self.assertEqual(soap.plan, "Use albuterol and acetaminophen")
        self.assertEqual({entity.vocabulary for entity in entities}, {"SNOMEDCT", "RxNorm"})
        self.assertTrue(any(entity.section == "plan" and entity.text.lower() == "albuterol" for entity in entities))

    def test_process_audio_to_note_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = write_synthetic_wav(Path(temp_dir) / "sample.wav")

            note = process_audio_to_note(wav_path, TranscriptionConfig(backend="metadata", chunk_seconds=0.5))

            validate_note_schema(note)
            self.assertEqual(set(note["soap"]), {"subjective", "objective", "assessment", "plan"})
            self.assertTrue(note["soap"]["subjective"])
            self.assertTrue(note["soap"]["objective"])
            self.assertEqual(note["audit"]["transcriber_backend"], "metadata")
            self.assertEqual(note["audit"]["network_attempts"], [])


if __name__ == "__main__":
    unittest.main()
