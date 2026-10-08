"""Evidence graph export for generated clinical-documentation drafts.

The graph is intentionally simple JSON so it can be inspected, diffed, and
loaded into downstream tooling without a database dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from offlinescribe.eval.metrics import flatten_note, score_pair, tokenize
from offlinescribe.eval.taxonomy import Encounter, EncounterNote
from offlinescribe.grounding.span_linker import link_spans
from offlinescribe.grounding.verifier import verify

SECTIONS = ("subjective", "objective", "assessment", "plan")


def build_evidence_graph(
    encounter: Encounter,
    generated: EncounterNote,
    *,
    condition: str,
    model: str,
    asr: str,
    seed: int = 0,
) -> dict[str, Any]:
    """Build a provenance graph for one generated note.

    Nodes represent the encounter, source transcript, generated sections, known
    synthetic gold entities, planted stressors, and verifier flags. Edges record
    what each section can be tied back to in the source transcript.
    """

    note_text = flatten_note(generated)
    metrics = score_pair(
        encounter.transcript,
        encounter.gold_note,
        generated,
        encounter.gold_meds,
        encounter.gold_entities,
    )
    nodes: list[dict[str, Any]] = [
        {
            "id": f"encounter:{encounter.encounter_id}",
            "type": "encounter",
            "label": encounter.encounter_id,
            "specialty": encounter.specialty,
        },
        {
            "id": "source:transcript",
            "type": "source",
            "label": "Synthetic source transcript",
            "token_count": len(tokenize(encounter.transcript)),
        },
        {
            "id": "note:draft",
            "type": "generated_note",
            "label": "Generated SOAP draft",
            "token_count": len(tokenize(note_text)),
        },
    ]
    edges: list[dict[str, Any]] = [
        {
            "source": f"encounter:{encounter.encounter_id}",
            "target": "source:transcript",
            "type": "HAS_SOURCE",
        },
        {
            "source": f"encounter:{encounter.encounter_id}",
            "target": "note:draft",
            "type": "HAS_DRAFT",
        },
    ]

    section_support: list[dict[str, Any]] = []
    for section in SECTIONS:
        text = getattr(generated, section)
        section_id = f"section:{section}"
        links = link_spans(text, encounter.transcript)
        supported = sum(1 for item in links if item["grounded"])
        unsupported = len(links) - supported
        ratio = supported / len(links) if links else 1.0
        unsupported_terms = sorted({str(item["span"]) for item in links if not item["grounded"]})
        nodes.append(
            {
                "id": section_id,
                "type": "note_section",
                "label": section,
                "token_count": len(tokenize(text)),
                "support_ratio": round(ratio, 4),
            }
        )
        edges.extend(
            [
                {"source": "note:draft", "target": section_id, "type": "HAS_SECTION"},
                {
                    "source": section_id,
                    "target": "source:transcript",
                    "type": "SUPPORTED_BY_SOURCE",
                    "score": round(ratio, 4),
                    "supported_terms": supported,
                    "unsupported_terms": unsupported,
                },
            ]
        )
        section_support.append(
            {
                "section": section,
                "support_ratio": round(ratio, 4),
                "supported_terms": supported,
                "unsupported_terms": unsupported,
                "top_unsupported_terms": unsupported_terms[:12],
            }
        )

    entity_coverage = _entity_coverage(encounter, note_text)
    for index, entity in enumerate(entity_coverage, start=1):
        node_id = f"entity:{index}"
        nodes.append(
            {
                "id": node_id,
                "type": "gold_entity",
                "label": entity["entity"],
                "present_in_source": entity["present_in_source"],
                "present_in_draft": entity["present_in_draft"],
            }
        )
        edges.append(
            {
                "source": node_id,
                "target": "source:transcript",
                "type": "MENTIONED_IN_SOURCE" if entity["present_in_source"] else "MISSING_FROM_SOURCE",
            }
        )
        edges.append(
            {
                "source": node_id,
                "target": "note:draft",
                "type": "MENTIONED_IN_DRAFT" if entity["present_in_draft"] else "OMITTED_FROM_DRAFT",
            }
        )

    planted_checks = _planted_checks(encounter, note_text)
    for index, planted in enumerate(planted_checks, start=1):
        node_id = f"planted:{index}"
        nodes.append({"id": node_id, "type": "planted_stressor", **planted})
        edges.append(
            {
                "source": node_id,
                "target": "note:draft",
                "type": "RECOVERED_IN_DRAFT" if planted["present_in_draft"] else "NOT_RECOVERED_IN_DRAFT",
            }
        )

    verifier_flags = verify(note_text, encounter.transcript)
    for index, flag in enumerate(verifier_flags, start=1):
        flag_id = f"verifier_flag:{index}"
        nodes.append({"id": flag_id, "type": "verifier_flag", "label": flag})
        edges.append({"source": flag_id, "target": "note:draft", "type": "FLAGS_DRAFT"})

    risk_summary = {
        **{key: round(value, 6) for key, value in metrics.items()},
        "mean_section_support": round(
            sum(item["support_ratio"] for item in section_support) / max(1, len(section_support)),
            6,
        ),
        "entities_recovered": sum(1 for item in entity_coverage if item["present_in_draft"]),
        "entities_expected": len(entity_coverage),
        "verifier_flag_count": len(verifier_flags),
    }

    return {
        "schema_version": "offlinescribe.evidence_graph.v1",
        "encounter_id": encounter.encounter_id,
        "run": {"condition": condition, "model": model, "asr": asr, "seed": seed},
        "nodes": nodes,
        "edges": edges,
        "section_support": section_support,
        "entity_coverage": entity_coverage,
        "planted_checks": planted_checks,
        "verifier_flags": verifier_flags,
        "risk_summary": risk_summary,
        "review_gate": _review_gate(risk_summary, verifier_flags),
    }


def write_evidence_graph(path: Path, graph: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _entity_coverage(encounter: Encounter, note_text: str) -> list[dict[str, Any]]:
    return [
        {
            "entity": entity,
            "present_in_source": _contains_phrase(encounter.transcript, entity),
            "present_in_draft": _contains_phrase(note_text, entity),
        }
        for entity in encounter.gold_entities
    ]


def _planted_checks(encounter: Encounter, note_text: str) -> list[dict[str, Any]]:
    checks = []
    for item in encounter.planted:
        token = str(item.get("token", ""))
        checks.append(
            {
                "label": token,
                "stressor_type": item.get("type", "unknown"),
                "present_in_source": _contains_phrase(encounter.transcript, token),
                "present_in_draft": _contains_phrase(note_text, token),
            }
        )
    return checks


def _review_gate(risk_summary: dict[str, float], verifier_flags: list[str]) -> dict[str, Any]:
    reasons = ["research_prototype_requires_named_human_review"]
    if risk_summary["omission_rate"] > 0:
        reasons.append("gold_entity_omission_detected")
    if risk_summary["hallucination_rate"] > 0.30:
        reasons.append("high_token_novelty_vs_source")
    if verifier_flags:
        reasons.extend(f"verifier:{flag}" for flag in verifier_flags)
    return {
        "status": "human_review_required",
        "release_to_ehr": False,
        "reasons": sorted(set(reasons)),
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase_tokens = tokenize(phrase)
    text_tokens = set(tokenize(text))
    return bool(phrase_tokens) and all(token in text_tokens for token in phrase_tokens)
