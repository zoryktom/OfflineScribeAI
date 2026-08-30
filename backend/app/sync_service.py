"""Background-style EHR sync.

Checks connectivity, maps pending visits to FHIR DocumentReference resources,
and POSTs them when not in dry-run. Failures are recorded and the visit stays
pending for retry. This module must never crash the rest of the app.

CLI:
    python -m app.sync_service --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TextIO

import httpx

from app.ehr.ehr_config import get_ehr_settings

from app.ehr.fhir_client import FhirAuthError, FhirClient, FhirRequestError
from app.ehr.fhir_mapper import FhirMappingError, visit_to_document_reference
from app.models import SyncRunResult, SyncStatus, SyncVisitResult, Visit
from app.storage_service import (
    init_db,
    list_pending_visits,
    mark_sync_failed,
    mark_synced,
)

logger = logging.getLogger(__name__)

SKIP_MISSING_CHART = "Missing patient link — cannot sync"
SKIP_NOT_REVIEWED = "skipped: not yet reviewed by provider"
DRY_RUN_PHI_WARNING = (
    "WARNING: dry-run output contains sample clinical data — "
    "do not paste this output anywhere public (issues, Slack, docs)."
)


def check_connectivity(timeout_seconds: float = 5.0) -> bool:
    """Return True if the configured FHIR base URL answers over HTTP. Never raises."""
    url = get_ehr_settings().fhir_base_url
    try:
        httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
        return True
    except httpx.HTTPError:
        return False


def sync_pending_visits(
    *,
    dry_run: bool = False,
    output: TextIO | None = None,
    db_path: Path | None = None,
    client: FhirClient | None = None,
) -> SyncRunResult:
    """Sync all pending visits. Safe to call from the API or a CLI."""
    init_db(db_path)
    results: list[SyncVisitResult] = []
    fhir_client = client or FhirClient()
    sink = output or sys.stdout

    if not dry_run and not check_connectivity():
        logger.warning("sync skipped: no internet connectivity")
        pending = list_pending_visits(db_path=db_path)
        return SyncRunResult(
            dry_run=False,
            results=[
                SyncVisitResult(
                    visit_id=visit.id,
                    sync_status=SyncStatus.pending,
                    error="No internet connection. The note is saved on this computer and will sync when online.",
                )
                for visit in pending
            ],
        )

    for visit in list_pending_visits(db_path=db_path):
        results.append(
            _sync_one(
                visit,
                client=fhir_client,
                dry_run=dry_run,
                sink=sink,
                db_path=db_path,
            )
        )

    return SyncRunResult(dry_run=dry_run, results=results)


def _sync_one(
    visit: Visit,
    *,
    client: FhirClient,
    dry_run: bool,
    sink: TextIO,
    db_path: Path | None = None,
) -> SyncVisitResult:
    if not visit.has_fhir_chart_link():
        logger.info(
            "sync skipped visit_id=%s reason=missing_fhir_patient_or_encounter",
            visit.id,
        )
        return SyncVisitResult(
            visit_id=visit.id,
            sync_status=SyncStatus.pending,
            dry_run=dry_run,
            error=SKIP_MISSING_CHART,
        )

    if not visit.is_reviewed():
        logger.info("sync skipped visit_id=%s reason=not_yet_reviewed_by_provider", visit.id)
        return SyncVisitResult(
            visit_id=visit.id,
            sync_status=SyncStatus.pending,
            dry_run=dry_run,
            error=SKIP_NOT_REVIEWED,
        )

    try:
        resource = visit_to_document_reference(visit)
    except FhirMappingError as exc:
        logger.error("sync mapping failed visit_id=%s error=%s", visit.id, exc)
        mark_sync_failed(visit.id, str(exc), db_path=db_path)
        return SyncVisitResult(
            visit_id=visit.id,
            sync_status=SyncStatus.pending,
            error=str(exc),
        )

    if dry_run:
        # Intentionally printed (not logged) so a clinician/IT person can inspect
        # the FHIR JSON before any sandbox call. Logger stays PHI-free.
        sink.write(DRY_RUN_PHI_WARNING + "\n")
        sink.write(f"--- dry-run DocumentReference for visit {visit.id} ---\n")
        sink.write(json.dumps(resource, indent=2))
        sink.write("\n")
        return SyncVisitResult(
            visit_id=visit.id,
            sync_status=SyncStatus.pending,
            dry_run=True,
        )

    try:
        resource_id = client.post_resource("DocumentReference", resource)
        mark_synced(visit.id, resource_id, db_path=db_path)
        logger.info("sync ok visit_id=%s fhir_resource_id=%s", visit.id, resource_id)
        return SyncVisitResult(
            visit_id=visit.id,
            sync_status=SyncStatus.synced,
            fhir_resource_id=resource_id,
        )
    except (FhirAuthError, FhirRequestError) as exc:
        logger.error("sync failed visit_id=%s error=%s", visit.id, exc)
        mark_sync_failed(visit.id, str(exc), db_path=db_path)
        return SyncVisitResult(
            visit_id=visit.id,
            sync_status=SyncStatus.pending,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 - sync must never take down the API
        logger.error("sync unexpected error visit_id=%s error=%s", visit.id, exc)
        mark_sync_failed(
            visit.id,
            "Unexpected sync error. The note is still saved locally.",
            db_path=db_path,
        )
        return SyncVisitResult(
            visit_id=visit.id,
            sync_status=SyncStatus.pending,
            error="Unexpected sync error. The note is still saved locally.",
        )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Sync pending Offline Scribe visits to FHIR.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print FHIR JSON locally. Does not send anything or need credentials.",
    )
    args = parser.parse_args(argv)
    result = sync_pending_visits(dry_run=args.dry_run)
    if not result.results:
        print("No pending visits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
