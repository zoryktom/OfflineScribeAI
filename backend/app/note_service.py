"""Convert a visit transcript into a structured SOAP note via a local Ollama model.

When STUB_MODE=true, returns a canned note so tests can run without Ollama.
When STUB_MODE=false, missing Ollama or a missing model fail with a clear,
actionable message — this runs in clinics with little IT support.

ICD-10 codes are never taken from the model. The model names diagnoses in
plain language; icd10_lookup.py maps those phrases onto a local CMS starter set.
"""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import get_settings
from app.grounding import apply_grounding
from app.icd10_lookup import lookup_diagnoses
from app.models import (
    FollowUpItem,
    GroundedSection,
    Note,
    NoteSource,
    SuggestedIcd10,
    TranscriptResult,
)
from app.negation_check import flag_negation_assertions
from app.prompts import SOAP_NOTE_SYSTEM_PROMPT, SOAP_NOTE_USER_PROMPT


class NoteGenerationError(Exception):
    """Raised when a SOAP note cannot be generated. Message is safe to show a clinician."""


def generate_note(transcript: str | TranscriptResult) -> Note:
    """Turn a visit transcript into a SOAP note. Never logs the transcript or note body."""
    settings = get_settings()
    prompt_transcript = _prompt_transcript(transcript)
    if not prompt_transcript:
        raise NoteGenerationError(
            "The transcript is empty, so a note cannot be generated. "
            "Re-record or upload the visit audio and try again."
        )

    if settings.stub_mode:
        note = _stub_note()
        note.verification_needs = flag_negation_assertions(
            {
                "subjective": note.subjective,
                "objective": note.objective,
                "assessment": note.assessment,
                "plan": note.plan,
            },
            prompt_transcript,
            transcript.segments if isinstance(transcript, TranscriptResult) else None,
        )
        return note

    _assert_ollama_ready()
    return _generate_with_ollama(prompt_transcript, transcript)


def _stub_note() -> Note:
    cough_source = NoteSource(
        start_s=2.4,
        end_s=7.1,
        text="I've had a cough for three days and a low fever.",
    )
    return Note(
        subjective=(
            "Patient reports a cough for three days with a low fever, and mild "
            "shortness of breath when walking uphill to the clinic."
        ),
        objective="Not documented in visit.",
        assessment=(
            "Possible acute respiratory illness. Differential includes viral upper "
            "respiratory infection. Suggested codes below are not confirmed diagnoses."
        ),
        plan=(
            "Supportive care discussed. Provider to complete exam findings and "
            "finalize the plan on review."
        ),
        suggested_icd10=[
            SuggestedIcd10(
                code="R05.9",
                description="Cough, unspecified",
                accepted=None,
            ),
            SuggestedIcd10(
                code="R50.9",
                description="Fever, unspecified",
                accepted=None,
            ),
        ],
        follow_up=[
            FollowUpItem(
                text="Return sooner if shortness of breath worsens or fever persists.",
                timeframe="48 hours if not improving",
            )
        ],
        subjective_grounding=GroundedSection(sources=[cough_source], directly_stated=True),
        objective_grounding=GroundedSection(sources=[], directly_stated=True),
        assessment_grounding=GroundedSection(sources=[cough_source], directly_stated=True),
        plan_grounding=GroundedSection(sources=[], directly_stated=True),
    )


def _assert_ollama_ready() -> None:
    """Fail with a clinic-actionable message if Ollama is down or the model is missing."""
    settings = get_settings()
    tags_url = settings.ollama_host.rstrip("/") + "/api/tags"
    try:
        request = Request(tags_url, method="GET")
        with urlopen(request, timeout=5) as response:  # noqa: S310 - local Ollama only
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise NoteGenerationError(
            "Ollama is not running, so a SOAP note cannot be generated. "
            "On this computer, open a terminal and run: ollama serve. "
            "Leave that window open, then try again."
        ) from exc
    except TimeoutError as exc:
        raise NoteGenerationError(
            "Ollama did not respond in time. Confirm it is running with: ollama serve. "
            f"Expected address: {settings.ollama_host}."
        ) from exc
    except json.JSONDecodeError as exc:
        raise NoteGenerationError(
            "Ollama responded, but the reply could not be read. "
            "Restart Ollama with `ollama serve` and try again."
        ) from exc

    names = [model.get("name", "") for model in payload.get("models", [])]
    if not _model_is_pulled(settings.ollama_model, names):
        raise NoteGenerationError(
            f"The local model '{settings.ollama_model}' is not installed. "
            f"In a terminal, run: ollama pull {settings.ollama_model} "
            "Wait until the download finishes (this can take several minutes), then try again."
        )


def _model_is_pulled(wanted: str, available: list[str]) -> bool:
    if wanted in available:
        return True
    return any(name == wanted or name.startswith(wanted + "-") for name in available)


# Clinical notes should stay consistent across re-runs of the same transcript.
# Ollama's default temperature (about 0.8) produced different Assessment
# language and ICD lookup phrases on identical visits. 0.2 reduces sampling
# noise; some local models behave oddly at literal 0, so we do not use zero.
_NOTE_TEMPERATURE = 0.2


def _generate_with_ollama(
    prompt_transcript: str,
    original: str | TranscriptResult,
) -> Note:
    settings = get_settings()
    generate_url = settings.ollama_host.rstrip("/") + "/api/generate"
    body = {
        "model": settings.ollama_model,
        "system": SOAP_NOTE_SYSTEM_PROMPT,
        "prompt": SOAP_NOTE_USER_PROMPT.format(transcript=prompt_transcript),
        "stream": False,
        "format": "json",
        "options": {"temperature": _NOTE_TEMPERATURE},
    }
    try:
        request = Request(
            generate_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(  # noqa: S310 - local Ollama only
            request, timeout=settings.ollama_timeout_seconds
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError as exc:
        raise NoteGenerationError(
            "The local model took too long to write the note. "
            "Try again, or use a smaller Ollama model in backend/.env (OLLAMA_MODEL)."
        ) from exc
    except URLError as exc:
        raise NoteGenerationError(
            "Could not reach Ollama while generating the note. "
            "Confirm `ollama serve` is still running and try again."
        ) from exc

    raw = payload.get("response", "")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(parsed, dict):
            raise ValueError("note payload is not an object")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise NoteGenerationError(
            "The local model returned a note that could not be read as JSON. "
            "Try generating again. If this keeps happening, the prompt in "
            "backend/app/prompts.py may need a small edit."
        ) from exc

    return _note_from_model_payload(parsed, original)


def _note_from_model_payload(
    parsed: dict,
    original: str | TranscriptResult,
) -> Note:
    segments = original.segments if isinstance(original, TranscriptResult) else []
    citations = parsed.get("citations") if isinstance(parsed.get("citations"), dict) else {}
    # Ignore any ICD-10 codes the model recalled. Codes come only from lookup.
    phrases = parsed.get("likely_diagnoses")
    if not isinstance(phrases, list):
        phrases = []

    sections: dict[str, tuple[str, GroundedSection]] = {}
    for name in ("subjective", "objective", "assessment", "plan"):
        raw_text = str(parsed.get(name) or "").strip()
        ranges = citations.get(name) if isinstance(citations.get(name), list) else None
        sections[name] = apply_grounding(
            raw_text, segments, ranges, section=name
        )

    follow_raw = parsed.get("follow_up") or []
    follow_up: list[FollowUpItem] = []
    if isinstance(follow_raw, list):
        for item in follow_raw:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            timeframe = item.get("timeframe")
            follow_up.append(
                FollowUpItem(
                    text=text,
                    timeframe=str(timeframe) if timeframe not in (None, "") else None,
                )
            )

    source_text = original.text if isinstance(original, TranscriptResult) else original
    verification_needs = flag_negation_assertions(
        {
            "subjective": sections["subjective"][0],
            "objective": sections["objective"][0],
            "assessment": sections["assessment"][0],
            "plan": sections["plan"][0],
        },
        source_text,
        segments,
    )

    return Note(
        subjective=sections["subjective"][0],
        objective=sections["objective"][0],
        assessment=sections["assessment"][0],
        plan=sections["plan"][0],
        suggested_icd10=lookup_diagnoses([str(p) for p in phrases]),
        follow_up=follow_up,
        subjective_grounding=sections["subjective"][1],
        objective_grounding=sections["objective"][1],
        assessment_grounding=sections["assessment"][1],
        plan_grounding=sections["plan"][1],
        verification_needs=verification_needs,
    )


def _prompt_transcript(transcript: str | TranscriptResult) -> str:
    """Build the text block inserted into SOAP_NOTE_USER_PROMPT.

    When timestamped segments exist, send those once (not duplicated after the
    full text). A 4096-token local context cannot afford the transcript twice.
    """
    if isinstance(transcript, str):
        return transcript.strip()
    if transcript.segments:
        parts = ["Timestamped segments:"]
        for index, segment in enumerate(transcript.segments):
            parts.append(
                f"[{index} | {segment.start_s:.1f}-{segment.end_s:.1f}s] {segment.text}"
            )
        return "\n".join(parts).strip()
    return transcript.text.strip()
