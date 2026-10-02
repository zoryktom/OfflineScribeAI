"""Build a 100-encounter synthetic corpus. No real PHI."""

from __future__ import annotations

import json
from pathlib import Path

from offlinescribe.eval.taxonomy import Encounter, EncounterNote

TEMPLATES = [
    {
        "specialty": "primary_care",
        "complaint": "follow-up hypertension and type 2 diabetes",
        "entity": "fatigue",
        "denied": "chest pain",
        "side": "left",
        "med": "lisinopril 10 mg",
        "plan": "continue lisinopril 10 mg daily and metformin 500 mg twice daily",
    },
    {
        "specialty": "ortho",
        "complaint": "ankle sprain after a stumble",
        "entity": "swelling",
        "denied": "numbness",
        "side": "right",
        "med": "ibuprofen 400 mg",
        "plan": "RICE, ibuprofen 400 mg as needed, follow up if worse",
    },
    {
        "specialty": "ent",
        "complaint": "ear fullness and tinnitus concern",
        "entity": "tinnitus",
        "denied": "otorrhea",
        "side": "left",
        "med": "fluticasone 50 mcg",
        "plan": "trial fluticasone 50 mcg, audiology if persists",
    },
    {
        "specialty": "pulmonary",
        "complaint": "cough for two weeks",
        "entity": "cough",
        "denied": "hemoptysis",
        "side": "right",
        "med": "albuterol 90 mcg",
        "plan": "albuterol 90 mcg as needed, chest x-ray if not improving",
    },
    {
        "specialty": "urology",
        "complaint": "dysuria and frequency",
        "entity": "dysuria",
        "denied": "hematuria",
        "side": "left",
        "med": "nitrofurantoin 100 mg",
        "plan": "nitrofurantoin 100 mg twice daily for five days",
    },
]


def build_encounter(idx: int) -> Encounter:
    tmpl = TEMPLATES[idx % len(TEMPLATES)]
    eid = f"E{idx:03d}"
    age = 28 + (idx % 50)
    laterality = tmpl["side"]
    transcript = (
        f"Clinician: What brings you in today? "
        f"Patient: I am here for {tmpl['complaint']}. "
        f"I have {tmpl['entity']} on the {laterality} side. "
        f"I deny {tmpl['denied']}. "
        f"I take {tmpl['med']}. "
        f"No fever overnight. "
        f"This started about {1 + idx % 10} weeks ago."
    )
    gold = EncounterNote(
        subjective=(
            f"{age}-year-old presents for {tmpl['complaint']}. "
            f"Reports {tmpl['entity']} on the {laterality} side. "
            f"Denies {tmpl['denied']}. Takes {tmpl['med']}."
        ),
        objective="Vitals reviewed. No new exam findings recorded in this synthetic fixture.",
        assessment=f"{tmpl['complaint']}. {tmpl['entity']} localized to the {laterality} side.",
        plan=tmpl["plan"],
    )
    planted = [
        {"type": "negation", "token": tmpl["denied"]},
        {"type": "laterality", "token": laterality},
        {"type": "medication", "token": tmpl["med"]},
    ]
    return Encounter(
        encounter_id=eid,
        specialty=tmpl["specialty"],
        transcript=transcript,
        gold_note=gold,
        gold_meds=[tmpl["med"]],
        gold_entities=[tmpl["entity"], tmpl["denied"], laterality],
        planted=planted,
    )


def write_manifest(path: Path, n: int = 100) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    transcripts = path.parent / "transcripts"
    gold_dir = path.parent / "gold_notes"
    transcripts.mkdir(exist_ok=True)
    gold_dir.mkdir(exist_ok=True)
    rows = [build_encounter(i) for i in range(1, n + 1)]
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json() + "\n")
            (transcripts / f"{row.encounter_id}.txt").write_text(row.transcript, encoding="utf-8")
            (gold_dir / f"{row.encounter_id}.json").write_text(
                row.gold_note.model_dump_json(indent=2),
                encoding="utf-8",
            )
    return path


def write_seed_annotations(manifest: Path, out_dir: Path) -> None:
    """Programmatic labels from planted tokens. Not human IAA."""
    out_dir.mkdir(parents=True, exist_ok=True)
    a1 = out_dir / "A1.jsonl"
    a2 = out_dir / "A2.jsonl"
    adj = out_dir / "adjudicated.jsonl"
    with manifest.open(encoding="utf-8") as src, a1.open("w", encoding="utf-8") as f1, a2.open(
        "w", encoding="utf-8"
    ) as f2, adj.open("w", encoding="utf-8") as fa:
        for line in src:
            enc = json.loads(line)
            for planted in enc["planted"]:
                row = {
                    "encounter_id": enc["encounter_id"],
                    "condition": "baseline",
                    "model": "stub",
                    "asr": "whisper-large-v3",
                    "span_generated": planted["token"],
                    "span_source": planted["token"],
                    "error_type": {
                        "negation": "negation_flip",
                        "laterality": "laterality",
                        "medication": "medication",
                    }[planted["type"]],
                    "severity": "moderate",
                    "clinically_significant": True,
                    "rationale": "seed label from planted token; not a human annotation",
                    "annotator_id": "A1",
                }
                f1.write(json.dumps(row) + "\n")
                row_b = dict(row)
                row_b["annotator_id"] = "A2"
                f2.write(json.dumps(row_b) + "\n")
                row_c = dict(row)
                row_c["annotator_id"] = "ADJ"
                fa.write(json.dumps(row_c) + "\n")


if __name__ == "__main__":
    root = Path("data/synthetic/manifest.jsonl")
    write_manifest(root, 100)
    write_seed_annotations(root, Path("data/annotations"))
    print(root)
