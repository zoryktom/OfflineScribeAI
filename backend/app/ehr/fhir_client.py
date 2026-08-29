"""SMART-on-FHIR OAuth2 client for Oracle Health (client-credentials / system account).

Step 1 of the build: no network calls. Token cache and POST helpers are present
so sync_service can be wired without talking to the sandbox yet.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.ehr.ehr_config import get_ehr_settings

logger = logging.getLogger(__name__)


class FhirAuthError(Exception):
    """Authentication failed. Message is safe to log (no clinical content)."""


class FhirRequestError(Exception):
    """A FHIR HTTP call failed. Message is safe to log (no clinical content)."""


class FhirClient:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_endpoint: str | None = None

    def get_access_token(self) -> str:
        """Return a cached token, refreshing if needed. Stub returns a placeholder."""
        settings = get_ehr_settings()
        if time.time() < self._token_expires_at - 30 and self._access_token:
            return self._access_token

        if not settings.cerner_client_id or not settings.cerner_client_secret:
            raise FhirAuthError(
                "Oracle Health client ID or secret is missing. Copy backend/.env.example "
                "to backend/.env and fill CERNER_CLIENT_ID and CERNER_CLIENT_SECRET "
                "from code Console, then retry sync."
            )

        # Step 1: do not call the authorization server.
        raise FhirAuthError(
            "Live SMART-on-FHIR token requests are not enabled in this scaffold. "
            "Run sync with --dry-run (no credentials required), or wait for step 5."
        )

    def post_resource(self, resource_type: str, body: dict[str, Any]) -> str:
        """POST a FHIR resource. Returns the new resource id.

        Oracle Health create responses are often empty-bodied; the new id is in
        the Location header (documented for DocumentReference create).
        """
        # Step 1: never send clinical data to the network.
        del resource_type, body
        raise FhirRequestError(
            "Live FHIR POST is not enabled in this scaffold. Use --dry-run to print "
            "the DocumentReference JSON locally, or wait for step 5."
        )

    def discover_token_endpoint(self) -> str:
        """Read token_endpoint from the tenant's SMART well-known document.

        Oracle Health documents that these URLs must be discovered rather than
        hardcoded, because they can change.
        TODO: verify the live well-known document still matches the sandbox
        example in the Authorization Framework docs.
        """
        if self._token_endpoint:
            return self._token_endpoint

        settings = get_ehr_settings()
        try:
            response = httpx.get(
                settings.smart_configuration_url,
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            document = response.json()
        except httpx.HTTPError as exc:
            raise FhirAuthError(
                "Could not read SMART configuration from the FHIR server. "
                "Check internet connectivity and FHIR_BASE_URL, then retry."
            ) from exc

        endpoint = document.get("token_endpoint")
        if not isinstance(endpoint, str) or not endpoint:
            raise FhirAuthError(
                "SMART configuration did not include token_endpoint. "
                "TODO: verify against Oracle Health FHIR R4 well-known SMART docs."
            )
        self._token_endpoint = endpoint
        return endpoint

    def _request_client_credentials_token(self, token_endpoint: str) -> tuple[str, int]:
        """Client-credentials token request (confidential system account).

        Oracle Health example uses HTTP Basic (client_id:client_secret) and
        application/x-www-form-urlencoded body with grant_type=client_credentials
        and a space-delimited scope parameter.
        TODO: verify whether this tenant's token_endpoint requires the
        `/hosts/{hostname}/` path segment from well-known vs the shorter path
        shown in some Authorization Framework curl examples.
        """
        settings = get_ehr_settings()
        try:
            response = httpx.post(
                token_endpoint,
                auth=(settings.cerner_client_id, settings.cerner_client_secret),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": " ".join(settings.scope_list),
                },
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            raise FhirAuthError(
                "Could not reach the Oracle Health token endpoint. "
                "Check internet connectivity and try again."
            ) from exc

        if response.status_code >= 400:
            raise FhirAuthError(
                f"Token request failed (HTTP {response.status_code}). "
                "Confirm the system app type, client secret, and scopes in code Console."
            )

        payload = response.json()
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 300)
        if not token:
            raise FhirAuthError(
                "Token response did not include access_token. "
                "TODO: verify against Oracle Health token endpoint docs."
            )
        return token, expires_in
