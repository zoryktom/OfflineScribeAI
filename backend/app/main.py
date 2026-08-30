"""Local-only FastAPI entry point. Bind with uvicorn --host 127.0.0.1."""

from __future__ import annotations

import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.asr_service import (
    AsrError,
    load_whisper_model,
    prepare_audio_for_asr,
    transcribe_audio,
    validate_audio_upload,
)
from app.auth import require_local_api_key
from app.config import get_settings
from app.models import (
    DemoEncounterRequest,
    HealthResponse,
    SyncRunResult,
    Visit,
    VisitUpdate,
)
from app.demo import (
    DEMO_UPLOAD_REFUSED,
    DemoError,
    export_visit_text,
    list_demo_scripts,
    load_demo_encounter,
    refuse_if_demo_upload,
    seed_walkthrough_visit,
)
from app.note_service import NoteGenerationError, generate_note
from app.startup_checks import StartupError, run_startup_checks
from app.storage_service import (
    StorageError,
    create_visit,
    get_visit,
    init_db,
    list_visits,
    purge_expired_visits,
    update_visit_note,
)
from app.sync_service import sync_pending_visits

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        run_startup_checks()
    except StartupError as exc:
        logger.error("startup refused: %s", exc)
        raise
    init_db()
    purge_expired_visits()
    settings = get_settings()
    if settings.demo_mode:
        seed_walkthrough_visit()
    if settings.asr_preload:
        load_whisper_model()
    yield


app = FastAPI(
    title="Offline Scribe",
    description="Local-first clinical scribe API. Not a hosted service.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        stub_mode=settings.stub_mode,
        ollama_model=settings.ollama_model,
        demo_mode=settings.demo_mode,
    )


@app.post("/visits", response_model=Visit, dependencies=[Depends(require_local_api_key)])
async def create_visit_from_audio(audio: UploadFile = File(...)) -> Visit:
    try:
        refuse_if_demo_upload()
    except DemoError as exc:
        raise HTTPException(status_code=403, detail=str(exc) or DEMO_UPLOAD_REFUSED) from exc
    settings = get_settings()
    upload_path: Path | None = None
    converted_path: Path | None = None
    try:
        try:
            suffix = validate_audio_upload(
                filename=audio.filename,
                content_type=audio.content_type,
            )
        except AsrError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        try:
            upload_path = await _buffer_upload(audio, suffix, settings.max_upload_bytes)
        except HTTPException:
            raise
        except OSError as exc:
            logger.error("could not buffer uploaded audio: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Could not save the recording on this computer. Check disk space and try again.",
            ) from exc

        logger.info("create_visit audio_bytes=%s", upload_path.stat().st_size)
        try:
            asr_path = prepare_audio_for_asr(upload_path)
            if asr_path != upload_path:
                converted_path = asr_path
            transcript = transcribe_audio(asr_path)
            note = generate_note(transcript)
            visit = create_visit(
                transcript.text,
                note,
                transcript_segments=transcript.segments,
                asr_flags=transcript.asr_flags,
            )
        except AsrError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except NoteGenerationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        logger.info("create_visit ok visit_id=%s", visit.id)
        return visit
    finally:
        if upload_path is not None:
            upload_path.unlink(missing_ok=True)
        if converted_path is not None:
            converted_path.unlink(missing_ok=True)


async def _buffer_upload(audio: UploadFile, suffix: str, max_bytes: int) -> Path:
    """Write the upload to a temp file. Rejects files above max_bytes with HTTP 413."""
    written = 0
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            temp_path = Path(handle.name)
            while True:
                chunk = await audio.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    limit_mb = max(1, max_bytes // (1024 * 1024))
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"That recording is larger than the {limit_mb} MB upload limit. "
                            "Record a shorter visit, or raise MAX_UPLOAD_BYTES in backend/.env."
                        ),
                    )
                handle.write(chunk)
        return temp_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


@app.get("/visits", response_model=list[Visit], dependencies=[Depends(require_local_api_key)])
def get_visits() -> list[Visit]:
    return list_visits()


@app.get("/visits/{visit_id}", response_model=Visit, dependencies=[Depends(require_local_api_key)])
def get_visit_by_id(visit_id: str) -> Visit:
    visit = get_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found on this computer.")
    return visit


@app.patch("/visits/{visit_id}", response_model=Visit, dependencies=[Depends(require_local_api_key)])
def patch_visit(visit_id: str, update: VisitUpdate) -> Visit:
    try:
        visit = update_visit_note(
            visit_id,
            update.note,
            reviewer_id=update.reviewer_id,
            section_actions=update.section_actions,
        )
    except StorageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found on this computer.")
    reviewer = visit.provider_review.reviewer_id if visit.provider_review else ""
    logger.info("visit updated visit_id=%s reviewer_id=%s", visit.id, reviewer)
    return visit


@app.get("/demo/scripts", dependencies=[Depends(require_local_api_key)])
def get_demo_scripts() -> list[dict[str, str]]:
    try:
        return list_demo_scripts()
    except DemoError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/demo/encounters", response_model=Visit, dependencies=[Depends(require_local_api_key)])
def create_demo_encounter(payload: DemoEncounterRequest) -> Visit:
    script = payload.script
    try:
        visit = load_demo_encounter(script)
    except DemoError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except NoteGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    logger.info("demo_encounter visit_id=%s", visit.id)
    return visit


@app.get("/visits/{visit_id}/export", dependencies=[Depends(require_local_api_key)])
def export_visit(visit_id: str) -> dict[str, str]:
    visit = get_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found on this computer.")
    return {"text": export_visit_text(visit)}


@app.post("/sync", response_model=SyncRunResult, dependencies=[Depends(require_local_api_key)])
def run_sync(dry_run: bool = False) -> SyncRunResult:
    logger.info("sync requested dry_run=%s", dry_run)
    try:
        return sync_pending_visits(dry_run=dry_run)
    except DemoError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
