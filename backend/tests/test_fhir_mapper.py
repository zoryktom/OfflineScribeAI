import base64
from datetime import datetime, timezone

from app.ehr.fhir_mapper import visit_to_document_reference
from app.models import Note, SuggestedIcd10, SyncStatus, Visit


def _sample_visit() -> Visit:
    return Visit(
        id="visit-test-1",
        timestamp=datetime(2026, 8, 28, 18, 0, tzinfo=timezone.utc),
        transcript="unused in mapper",
        note=Note(
            subjective="Cough for three days.",
            objective="Lungs not yet documented.",
            assessment="Possible viral illness.",
            plan="Supportive care.",
            suggested_icd10=[
                SuggestedIcd10(
                    code="R05.9",
                    description="Cough, unspecified",
                    accepted=True,
                )
            ],
        ),
        sync_status=SyncStatus.pending,
        fhir_patient_id="12457977",
        fhir_encounter_id="97987761",
    )


def test_document_reference_has_required_r4_fields():
    resource = visit_to_document_reference(_sample_visit())

    assert resource["resourceType"] == "DocumentReference"
    assert resource["status"] == "current"
    assert resource["docStatus"] == "final"
    assert resource["subject"]["reference"] == "Patient/12457977"
    assert resource["author"][0]["reference"].startswith("Practitioner/")

    coding = resource["type"]["coding"]
    assert len(coding) == 1
    assert coding[0]["system"] == (
        "https://fhir.cerner.com/ec2458f2-1e24-41c8-b71b-0e701af7583d/codeSet/72"
    )
    assert coding[0]["code"] == "2820507"
    assert coding[0]["display"] == "Admission Note Physician"
    # Oracle Health: do not mix LOINC with proprietary Code Set 72 in one type.
    assert coding[0]["system"] != "http://loinc.org"
    assert all(item.get("system") != "http://loinc.org" for item in coding)

    assert len(resource["content"]) == 1
    attachment = resource["content"][0]["attachment"]
    assert attachment["contentType"].startswith("text/plain")
    decoded = base64.b64decode(attachment["data"]).decode("utf-8")
    assert "SUBJECTIVE" in decoded
    assert "Cough for three days." in decoded

    context = resource["context"]
    assert context["encounter"][0]["reference"] == "Encounter/97987761"
    assert "end" in context["period"]
    assert "T" in context["period"]["end"]
