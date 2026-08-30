"""Map an internal Visit/Note to a FHIR R4 DocumentReference for Oracle Health.

Built from the Oracle Health Millennium "Create a document reference" page
(required fields, MIME types, context.period.end, Location-header create
response). Where a field might still be tenant-specific, a TODO remains.

This module does not send anything over the network.
"""

from __future__ import annotations

import base64
import json
from datetime import timedelta
from typing import Any

from app.ehr.ehr_config import get_ehr_settings
from app.models import Note, Visit


class FhirMappingError(Exception):
    """Visit is missing data required to build a DocumentReference."""


def visit_to_document_reference(visit: Visit) -> dict[str, Any]:
    """Return a FHIR R4 DocumentReference dict ready to POST (or print in dry-run)."""
    settings = get_ehr_settings()
    if not visit.has_fhir_chart_link():
        raise FhirMappingError(
            f"Visit {visit.id} has no FHIR patient/encounter link, so it cannot be synced."
        )

    created = visit.timestamp
    period_end = created + timedelta(minutes=30)
    note_text = format_note_as_plain_text(visit.note)
    if visit.watermark:
        note_text = f"{visit.watermark}\n\n{note_text}"
    encoded = base64.b64encode(note_text.encode("utf-8")).decode("ascii")

    resource: dict[str, Any] = {
        "resourceType": "DocumentReference",
        "status": "current",
        "docStatus": "final",
        # Oracle Health: type must be LOINC *or* a proprietary Code Set 72 coding,
        # not both in the same request. The published create example uses Code Set 72.
        # TODO: verify against Oracle Health FHIR R4 docs whether a LOINC type
        # (e.g. 34117-2) is accepted on create for this tenant. Do not send both.
        "type": {
            "coding": [
                {
                    "system": settings.document_type_system,
                    "code": settings.document_type_code,
                    "display": settings.document_type_display,
                    "userSelected": True,
                }
            ],
            "text": settings.document_type_display,
        },
        "subject": {"reference": f"Patient/{visit.fhir_patient_id}"},
        # Author is required in the create schema. For system (client-credentials)
        # access Oracle Health documents author as optional; we still send the
        # configured sandbox practitioner so the payload matches the example body.
        # TODO: verify the practitioner id is valid on the target tenant.
        "author": [
            {"reference": f"Practitioner/{settings.fhir_practitioner_id}"}
        ],
        "content": [
            {
                "attachment": {
                    # text/plain is in the documented supported MIME list.
                    "contentType": "text/plain;charset=utf-8",
                    "data": encoded,
                    "title": "Offline Scribe SOAP note",
                    "creation": _fhir_instant(created),
                }
            }
        ],
        "context": {
            "encounter": [
                {"reference": f"Encounter/{visit.fhir_encounter_id}"}
            ],
            # period.end is required; all dates must include a time component.
            "period": {
                "start": _fhir_instant(created),
                "end": _fhir_instant(period_end),
            },
        },
    }
    return resource


def format_note_as_plain_text(note: Note) -> str:
    """Render the SOAP note as text for the DocumentReference attachment."""
    icd_lines = []
    for item in note.suggested_icd10:
        review = "accepted" if item.accepted else "not accepted"
        if item.accepted is None:
            review = "not reviewed"
        icd_lines.append(f"- {item.code} {item.description} ({review})")
    follow_lines = []
    for item in note.follow_up:
        extra = f" ({item.timeframe})" if item.timeframe else ""
        follow_lines.append(f"- {item.text}{extra}")

    sections = [
        "SUBJECTIVE",
        note.subjective.strip() or "Not documented in visit",
        "",
        "OBJECTIVE",
        note.objective.strip() or "Not documented in visit",
        "",
        "ASSESSMENT",
        note.assessment.strip() or "Not documented in visit",
        "",
        "PLAN",
        note.plan.strip() or "Not documented in visit",
        "",
        "SUGGESTED ICD-10",
        "\n".join(icd_lines) if icd_lines else "None",
        "",
        "FOLLOW-UP",
        "\n".join(follow_lines) if follow_lines else "None",
    ]
    return "\n".join(sections)


def document_reference_json(visit: Visit) -> str:
    return json.dumps(visit_to_document_reference(visit), indent=2)


def _fhir_instant(value: Any) -> str:
    """Format a datetime as an ISO-8601 instant with a time component."""
    text = value.isoformat()
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    # TODO: verify Oracle Health's required fractional-second precision.
    return text
