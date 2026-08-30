"""Planted-error measurement harness. Does not tune lexicons to pass fixtures.

Synthetic fixtures only. Not a clinical validation set.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from app.asr_flags import flag_asr_concerns
from app.grounding import apply_grounding
from app.models import Note, SpeakerTurn, TranscriptResult
from app.negation_check import flag_negation_assertions
from app.negation_llm import classify_assertion_needs
from app.note_service import generate_note

_LLM_FLAG_REASONS = frozenset({"denied_by_patient", "only_asked_not_confirmed"})

_BACKEND = Path(__file__).resolve().parent.parent
_FIXTURES_PATH = _BACKEND / "tests" / "eval" / "fixtures.json"
_DIALOGUE_DIR = _BACKEND.parent / "audio_samples"
_ENCOUNTER_SCRIPTS = (
    "synthetic_clinic_visit_dialogue.txt",
    "synthetic_htn_diabetes_followup_dialogue.txt",
    "synthetic_ankle_sprain_dialogue.txt",
    "synthetic_ambiguous_visit_dialogue.txt",
)


def load_fixtures(path: Path | None = None) -> list[dict]:
    payload = json.loads((path or _FIXTURES_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Eval fixtures must be a JSON list.")
    return payload


def turns_to_transcript(turns: list[dict]) -> TranscriptResult:
    segments: list[SpeakerTurn] = []
    spoken: list[str] = []
    cursor = 0.0
    for raw in turns:
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        speaker = raw.get("speaker") or "unknown"
        if speaker not in ("provider", "patient", "unknown"):
            speaker = "unknown"
        duration = max(1.5, len(text.split()) * 0.35)
        segments.append(
            SpeakerTurn(
                speaker=speaker,
                start_s=cursor,
                end_s=cursor + duration,
                text=text,
            )
        )
        cursor += duration
        spoken.append(text)
    return TranscriptResult(text=" ".join(spoken), segments=segments)


def evaluate_fixture(fixture: dict, *, generated: Note | None = None) -> dict:
    """Measure whether current checks catch one planted synthetic error."""
    transcript = turns_to_transcript(fixture.get("turns") or [])
    planted = str(fixture.get("planted_token") or "").strip().lower()
    failure_type = str(fixture.get("failure_type") or "")
    expected = str(fixture.get("expected_mechanism") or "")
    probe = str(fixture.get("probe_assertion") or "").strip()
    role = str(fixture.get("role") or "planted_error")
    probe_section = str(fixture.get("probe_section") or "").strip()

    asr_flags = flag_asr_concerns(transcript.segments)
    note = generated if generated is not None else generate_note(transcript)
    pipeline_negation = list(note.verification_needs)

    probe_negation = []
    if probe:
        sections = {
            "subjective": "",
            "objective": "Not documented in visit.",
            "assessment": "",
            "plan": "",
        }
        if role == "benign" and probe_section in sections:
            sections[probe_section] = probe
        elif failure_type == "family_history_miscite":
            sections["assessment"] = probe
        else:
            sections["subjective"] = probe
        probe_negation = flag_negation_assertions(
            sections,
            transcript.text,
            transcript.segments,
        )
        probe_llm = classify_assertion_needs(
            sections,
            transcript.text,
            transcript.segments,
        )
    else:
        probe_llm = []

    grounding_sources: list[str] = []
    if probe and expected == "grounding":
        section = "assessment" if failure_type == "family_history_miscite" else "subjective"
        _text, grounded = apply_grounding(
            probe, transcript.segments, None, section=section
        )
        grounding_sources = [item.text for item in grounded.sources]

    caught = False
    caught_by: str | None = None
    llm_flagged = any(item.reason in _LLM_FLAG_REASONS for item in probe_llm)
    keyword_flagged = any(item.reason == "negation_or_question" for item in probe_negation)

    if role == "benign":
        false_positive = llm_flagged
        return {
            "id": fixture.get("id"),
            "role": role,
            "failure_type": failure_type,
            "expected_mechanism": expected,
            "planted_token": planted,
            "should_flag": False,
            "caught": False,
            "false_positive": false_positive,
            "false_positive_old": keyword_flagged,
            "false_positive_new": llm_flagged,
            "caught_old": False,
            "caught_new": False,
            "caught_by": "negation_llm" if false_positive else None,
            "pipeline_verification_need_count": len(pipeline_negation),
            "probe_negation_flag_count": len(probe_negation),
            "probe_llm_flag_count": len(probe_llm),
            "asr_flag_count": len(asr_flags),
            "asr_flag_reasons": [flag.reason for flag in asr_flags],
            "grounding_source_count": 0,
            "stub_or_live_note_has_verification_needs": bool(pipeline_negation),
        }

    if failure_type == "denied_symptom_outside_lexicon":
        if llm_flagged:
            caught = True
            caught_by = "negation_llm"
        elif keyword_flagged:
            caught = True
            caught_by = "negation_check"
    elif failure_type == "garbled_drug_outside_list":
        if any(planted and planted in flag.text.lower() for flag in asr_flags):
            caught = True
            caught_by = "asr_flags"
    elif failure_type == "family_history_miscite":
        family_hit = any(
            planted in source.lower() or "stroke" in source.lower()
            for source in grounding_sources
        )
        # Caught means the planted family-history span was not cited on Assessment.
        if not family_hit:
            caught = True
            caught_by = "grounding"
    elif failure_type == "paraphrase_symptom":
        if grounding_sources:
            caught = True
            caught_by = "grounding"

    return {
        "id": fixture.get("id"),
        "role": role,
        "failure_type": failure_type,
        "expected_mechanism": expected,
        "planted_token": planted,
        "should_flag": True,
        "caught": caught,
        "false_positive": False,
        "false_positive_old": False,
        "false_positive_new": False,
        "caught_old": keyword_flagged if failure_type == "denied_symptom_outside_lexicon" else caught,
        "caught_new": llm_flagged if failure_type == "denied_symptom_outside_lexicon" else caught,
        "caught_by": caught_by,
        "pipeline_verification_need_count": len(pipeline_negation),
        "probe_negation_flag_count": len(probe_negation),
        "probe_llm_flag_count": len(probe_llm),
        "asr_flag_count": len(asr_flags),
        "asr_flag_reasons": [flag.reason for flag in asr_flags],
        "grounding_source_count": len(grounding_sources),
        "stub_or_live_note_has_verification_needs": bool(pipeline_negation),
    }


def summarize(rows: list[dict]) -> dict:
    planted = [row for row in rows if row.get("role") != "benign"]
    benign = [row for row in rows if row.get("role") == "benign"]
    by_type: dict[str, dict[str, int]] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["failure_type"])].append(row)
    for failure_type, items in grouped.items():
        planted_items = [item for item in items if item.get("role") != "benign"]
        benign_items = [item for item in items if item.get("role") == "benign"]
        by_type[failure_type] = {
            "caught": sum(1 for item in planted_items if item["caught"]),
            "planted_total": len(planted_items),
            "false_positives": sum(1 for item in benign_items if item.get("false_positive")),
            "benign_total": len(benign_items),
        }
    by_mechanism: dict[str, dict[str, int]] = {}
    for mechanism in sorted({str(row.get("expected_mechanism") or "") for row in rows}):
        planted_m = [row for row in planted if row.get("expected_mechanism") == mechanism]
        benign_m = [row for row in benign if row.get("expected_mechanism") == mechanism]
        by_mechanism[mechanism] = {
            "caught": sum(1 for row in planted_m if row["caught"]),
            "planted_total": len(planted_m),
            "false_positives": sum(1 for row in benign_m if row.get("false_positive")),
            "benign_total": len(benign_m),
        }
    denied = [row for row in planted if row.get("failure_type") == "denied_symptom_outside_lexicon"]
    comparison = {
        "negation_check_keyword": {
            "caught": sum(1 for row in denied if row.get("caught_old")),
            "planted_total": len(denied),
            "false_positives": sum(1 for row in benign if row.get("false_positive_old")),
            "benign_total": len(benign),
        },
        "negation_llm": {
            "caught": sum(1 for row in denied if row.get("caught_new")),
            "planted_total": len(denied),
            "false_positives": sum(1 for row in benign if row.get("false_positive_new")),
            "benign_total": len(benign),
        },
    }
    return {
        "fixture_count": len(rows),
        "planted_count": len(planted),
        "benign_count": len(benign),
        "caught_count": sum(1 for row in planted if row["caught"]),
        "false_positive_count": sum(1 for row in benign if row.get("false_positive")),
        "by_type": by_type,
        "by_mechanism": by_mechanism,
        "comparison": comparison,
        "results": rows,
    }


def format_text_report(report: dict) -> str:
    lines = [
        "Planted-error eval (synthetic fixtures). Not clinical validation.",
        (
            f"Caught {report['caught_count']} / {report['planted_count']} planted errors. "
            f"False positives {report['false_positive_count']} / {report['benign_count']} "
            "benign fixtures."
        ),
        "",
        "By mechanism:",
    ]
    comparison = report.get("comparison") or {}
    if comparison:
        lines.append("Negation comparison (same denied + benign fixtures):")
        for name, counts in comparison.items():
            lines.append(
                f"  {name}: {counts['caught']}/{counts['planted_total']} catches, "
                f"{counts['false_positives']}/{counts['benign_total']} false positives"
            )
        lines.append("")
    for mechanism, counts in report["by_mechanism"].items():
        lines.append(
            f"  {mechanism}: {counts['caught']}/{counts['planted_total']} catches, "
            f"{counts['false_positives']}/{counts['benign_total']} false positives "
            "on benign fixtures"
        )
    lines.append("")
    for failure_type, counts in report["by_type"].items():
        if counts["planted_total"]:
            lines.append(
                f"{failure_type}: {counts['caught']}/{counts['planted_total']} caught"
            )
        if counts["benign_total"]:
            lines.append(
                f"{failure_type}: {counts['false_positives']}/{counts['benign_total']} "
                "false positives"
            )
    lines.append("")
    for row in report["results"]:
        if row.get("role") == "benign":
            mark = "false_positive" if row.get("false_positive") else "true_negative"
        else:
            mark = "caught" if row["caught"] else "missed"
        lines.append(
            f"- {row['id']}: {mark} (expected {row['expected_mechanism']}, "
            f"caught_by={row['caught_by']})"
        )
    return "\n".join(lines) + "\n"


def run_harness(path: Path | None = None) -> dict:
    rows = [evaluate_fixture(item) for item in load_fixtures(path)]
    return summarize(rows)


def load_encounter_transcript(script_name: str) -> TranscriptResult:
    path = _DIALOGUE_DIR / script_name
    segments: list[SpeakerTurn] = []
    spoken: list[str] = []
    cursor = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not (line.startswith("PROVIDER:") or line.startswith("PATIENT:")):
            continue
        role, body = line.split(":", 1)
        text = body.strip()
        speaker = "provider" if role == "PROVIDER" else "patient"
        duration = max(2.0, len(text.split()) * 0.35)
        segments.append(
            SpeakerTurn(speaker=speaker, start_s=cursor, end_s=cursor + duration, text=text)
        )
        cursor += duration
        spoken.append(text)
    return TranscriptResult(text=" ".join(spoken), segments=segments)


def run_live_encounters(*, repeats: int = 2) -> list[dict]:
    """Run generate_note + flaggers on the four synthetic encounter scripts."""
    from app.config import clear_settings_cache, get_settings

    settings = get_settings()
    if settings.stub_mode:
        raise RuntimeError(
            "Live eval requires STUB_MODE=false. Set it in the environment and retry."
        )
    findings: list[dict] = []
    for script in _ENCOUNTER_SCRIPTS:
        transcript = load_encounter_transcript(script)
        asr_flags = flag_asr_concerns(transcript.segments)
        for run_index in range(1, repeats + 1):
            started = time.perf_counter()
            note = generate_note(transcript)
            note_s = time.perf_counter() - started
            from app.negation_llm import last_classify_seconds

            findings.append(
                {
                    "script": script,
                    "run": run_index,
                    "model": settings.ollama_model,
                    "note_seconds": round(note_s, 2),
                    "classify_seconds": last_classify_seconds(),
                    "verification_need_count": len(note.verification_needs),
                    "verification_reasons": [
                        item.reason for item in note.verification_needs
                    ],
                    "verification_sections": [
                        item.section for item in note.verification_needs
                    ],
                    "asr_flag_count": len(asr_flags),
                    "asr_flag_reasons": [flag.reason for flag in asr_flags],
                    "icd_codes": [item.code for item in note.suggested_icd10],
                    "soap_char_counts": {
                        "subjective": len(note.subjective),
                        "objective": len(note.objective),
                        "assessment": len(note.assessment),
                        "plan": len(note.plan),
                    },
                    "assessment_abridged": (note.assessment or "")[:180],
                    "subjective_abridged": (note.subjective or "")[:180],
                }
            )
            clear_settings_cache()
    findings.append(_investigate_zero_flags(findings))
    return findings


def _investigate_zero_flags(findings: list[dict]) -> dict:
    """If live output produced no flags, check whether the flaggers still fire."""
    encounter_rows = [row for row in findings if "script" in row]
    negation_total = sum(row.get("verification_need_count", 0) for row in encounter_rows)
    asr_total = sum(row.get("asr_flag_count", 0) for row in encounter_rows)
    probe: dict[str, object] = {
        "script": "investigation",
        "run": 0,
        "live_negation_flags_total": negation_total,
        "live_asr_flags_total": asr_total,
    }
    if negation_total == 0:
        ambiguous = load_encounter_transcript("synthetic_ambiguous_visit_dialogue.txt")
        probe_flags = flag_negation_assertions(
            {
                "subjective": "The patient has fever and shortness of breath at rest.",
                "objective": "",
                "assessment": "",
                "plan": "",
            },
            ambiguous.text,
            ambiguous.segments,
        )
        probe["negation_checker_on_known_assertion"] = len(probe_flags)
        probe["negation_investigation"] = (
            "Live notes produced zero verification_needs. "
            "The checker still flags an asserted fever/SOB sentence against the "
            "ambiguous script."
            if probe_flags
            else "Live notes produced zero verification_needs, and the checker "
            "also missed a known asserted fever/SOB sentence. Treat as a bug."
        )
    if asr_total == 0:
        liz = flag_asr_concerns(
            [
                SpeakerTurn(
                    speaker="unknown",
                    start_s=1.0,
                    end_s=4.0,
                    text="I still take the liz in April 10 mg.",
                )
            ]
        )
        probe["asr_checker_on_known_garble"] = len(liz)
        probe["asr_investigation"] = (
            "Encounter scripts use correctly spelled drug names, so asr_flags "
            "were empty. The checker still flags the known 'liz' garble."
            if liz
            else "asr_flags was empty on scripts and also missed the known "
            "'liz' garble. Treat as a bug."
        )
    return probe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure planted-error catch rates on synthetic fixtures."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also run the four encounter scripts through generate_note (STUB_MODE=false).",
    )
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    if args.live:
        live = run_live_encounters(repeats=args.repeats)
        sys.stdout.write("Live encounter runs (abridged; synthetic scripts only):\n")
        sys.stdout.write(json.dumps(live, indent=2))
        sys.stdout.write("\n")
        return 0
    report = run_harness()
    sys.stdout.write(format_text_report(report))
    sys.stdout.write("\n")
    sys.stdout.write(json.dumps(report, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
