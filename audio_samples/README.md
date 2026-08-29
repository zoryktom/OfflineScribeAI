# Audio samples

**Synthetic / mock clinical language only. Not real patient information.**

Do not add recordings that contain identifiable patient speech.

## Committed

| File | Role |
| --- | --- |
| `english_speech_sample.wav` | Short synthetic English speech (macOS `say`) for the ASR unit test. Not a visit recording. |
| `*_dialogue.txt` | Written mock clinician–patient scripts used to synthesize longer evaluation audio. |

## Not committed (gitignored)

Longer `.wav` files are omitted from git because they are large binaries and can be regenerated from the dialogue scripts:

- `synthetic_clinic_visit.wav`
- `synthetic_htn_diabetes_followup.wav`
- `synthetic_ankle_sprain.wav`
- `synthetic_ambiguous_visit.wav`
- `placeholder_visit.wav` (silence; real ASR fails with “no speech detected”)

Those visit recordings were produced with macOS two-voice text-to-speech (Samantha / Fred) from the matching `*_dialogue.txt` files. Exact waveforms will not match a new TTS run, so ASR transcripts can differ slightly from the original evaluation logs.

## Labels in the dialogue files

Each `*_dialogue.txt` file starts with an explicit “SYNTHETIC TEST DATA — NOT REAL PATIENT INFORMATION” header. Names, medications, and vitals in those scripts are invented fixtures.
