"""Deterministic stub generator so ablations run without Ollama.

Conditions follow docs/study_design.md. This is not a clinical model.
"""

from __future__ import annotations

import copy
import hashlib
import re

from offlinescribe.eval.taxonomy import Encounter, EncounterNote


def generate_note(
    encounter: Encounter,
    *,
    condition: str,
    model: str,
    asr: str,
    seed: int = 0,
) -> EncounterNote:
    """Return a SOAP draft derived from the gold note plus condition-specific noise."""
    note = copy.deepcopy(encounter.gold_note)
    key = f"{encounter.encounter_id}|{condition}|{model}|{asr}|{seed}"
    roll = int(hashlib.sha256(key.encode()).hexdigest(), 16)

    if condition == "baseline":
        note = _inject_hallucination(note, roll)
        note = _drop_entity(note, encounter, roll)
    elif condition == "rag":
        note = _inject_hallucination(note, roll // 3)
        note = _drop_entity(note, encounter, roll)
    elif condition == "rag_grounded":
        note = _drop_entity(note, encounter, roll * 2)
    elif condition == "rag_grounded_verified":
        note = _drop_entity(note, encounter, roll // 5)
    else:
        raise ValueError(f"Unknown condition {condition!r}. See docs/study_design.md.")

    if "whisper-tiny" in asr or "whisper-medium" in asr:
        note.subjective = _garble_meds(note.subjective, encounter.gold_meds, roll)
    return note


def _inject_hallucination(note: EncounterNote, roll: int) -> EncounterNote:
    extras = (
        " Patient is well controlled on all medications.",
        " No known drug allergies were confirmed in this visit.",
        " Family history of early stroke is attributed to the patient.",
    )
    if roll % 3 == 0:
        note.assessment = (note.assessment + extras[roll % len(extras)]).strip()
    return note


def _drop_entity(note: EncounterNote, encounter: Encounter, roll: int) -> EncounterNote:
    if not encounter.gold_entities:
        return note
    token = encounter.gold_entities[roll % len(encounter.gold_entities)]
    pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
    note.subjective = pattern.sub("", note.subjective)
    note.subjective = re.sub(r"\s+", " ", note.subjective).strip()
    return note


def _garble_meds(text: str, meds: list[str], roll: int) -> str:
    if not meds or roll % 2:
        return text
    garbles = {
        "lisinopril": "liz in April",
        "metformin": "met for men",
        "atorvastatin": "adorvastatin",
    }
    out = text
    for correct, wrong in garbles.items():
        out = re.sub(rf"\b{correct}\b", wrong, out, flags=re.IGNORECASE)
    return out
