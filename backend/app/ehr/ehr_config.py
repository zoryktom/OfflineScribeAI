"""Oracle Health / Cerner sandbox connection settings.

Sandbox URLs below are taken from Oracle Health Millennium FHIR R4 docs
(service root URL and authorization framework). Switching from the public
sandbox to a real tenant is a config change for *this file / .env* — but
going live against a real health system also requires a business agreement
and BAA. The app will not bypass that.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import _BACKEND_DIR

# Public Oracle Health developer sandbox tenant (documented service root URL).
SANDBOX_TENANT_ID = "ec2458f2-1e24-41c8-b71b-0e701af7583d"
SANDBOX_FHIR_BASE_URL = (
    f"https://fhir-ehr-code.cerner.com/r4/{SANDBOX_TENANT_ID}"
)

# SMART v1 system scopes for a backend (client-credentials) app that writes notes.
# Wildcard scopes are not supported by Oracle Health; list each resource explicitly.
# TODO: verify against the scopes enabled on the app in code Console. SMART v2 uses
# a different scope syntax (e.g. system/DocumentReference.cu) if the app is
# registered as SMART v2.
DEFAULT_OAUTH_SCOPES = (
    "system/DocumentReference.write "
    "system/DocumentReference.read "
    "system/Patient.read "
    "system/Encounter.read"
)


class EhrSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    use_sandbox: bool = True
    fhir_base_url: str = SANDBOX_FHIR_BASE_URL
    tenant_id: str = SANDBOX_TENANT_ID
    oauth_scopes: str = DEFAULT_OAUTH_SCOPES

    # Never hardcode secrets. Read from backend/.env.
    cerner_client_id: str = ""
    cerner_client_secret: str = ""

    # Optional; used when building DocumentReference.author for system access.
    fhir_practitioner_id: str = "3332064"

    # DocumentReference.type from Oracle Health's published create example.
    # Type must be LOINC *or* proprietary Code Set 72, not both.
    # TODO: verify against Oracle Health FHIR R4 docs whether LOINC (e.g. 34117-2)
    # is accepted on *create* for this tenant. Do not send both together.
    document_type_code: str = "2820507"
    document_type_display: str = "Admission Note Physician"
    document_type_code_set: str = "72"

    @property
    def smart_configuration_url(self) -> str:
        return self.fhir_base_url.rstrip("/") + "/.well-known/smart-configuration"

    @property
    def document_type_system(self) -> str:
        return f"https://fhir.cerner.com/{self.tenant_id}/codeSet/{self.document_type_code_set}"

    @property
    def document_reference_url(self) -> str:
        return self.fhir_base_url.rstrip("/") + "/DocumentReference"

    @property
    def scope_list(self) -> list[str]:
        return [scope for scope in self.oauth_scopes.split() if scope]


@lru_cache
def get_ehr_settings() -> EhrSettings:
    return EhrSettings()


def clear_ehr_settings_cache() -> None:
    get_ehr_settings.cache_clear()
