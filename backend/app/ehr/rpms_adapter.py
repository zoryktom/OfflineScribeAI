"""RPMS adapter — not implemented.

Indian Health Service RPMS (Resource and Patient Management System) is the EHR
used by many rural and frontier clinics this product hopes to serve. It does
**not** expose a FHIR write API comparable to Oracle Health Millennium.

This module exists so the rest of Offline Scribe can keep a single
`sync_service` boundary. Do not implement a live RPMS connection here: it is
site-specific integration work, not a config flag.
"""

from __future__ import annotations

from typing import Any

from app.models import Visit


class RpmsNotImplementedError(NotImplementedError):
    """Raised if anyone accidentally calls the RPMS stub."""


def sync_visit(_visit: Visit) -> dict[str, Any]:
    """Do not call. RPMS integration is out of scope for this version.

    What a real site integration would need (documented, not built):

    1. **Interface style.** Typical RPMS sites exchange data through HL7v2
       (often via a local interface engine) and/or VistA-style RPCs / FileMan
       updates, not FHIR R4 REST. There is no public, tenant-portable
       "POST DocumentReference" equivalent.

    2. **Document message.** A progress note or H&P is commonly sent as an
       MDM^T02 (or site-agreed variant) with a TXA/OBX payload, or as a TIU
       document via a VistA RPC. The exact event, encoding characters, and
       receiving application names are assigned by *that* facility.

    3. **Identifiers.** Patient DFN / HRN, visit IEN, location, and author DUZ
       are local to the RPMS instance. Offline Scribe's sandbox FHIR Patient
       and Encounter ids will not work.

    4. **Contracts.** Connectivity usually requires an agreement with the
       service unit / area office, a BAA, and coordinated testing on a
       non-production RPMS account. That is a relationship step.

    5. **Operations.** Someone on site must operate an interface engine (or
       equivalent), map our SOAP text into the local TIU note title, and
       monitor HL7 acknowledgements. Offline Scribe should keep visits
       `pending` until that acknowledgement is understood.

    Until a named facility sponsors that work, this adapter stays a stub.
    """
    raise RpmsNotImplementedError(
        "RPMS is not available in this version. Sync uses Oracle Health FHIR "
        "when USE_SANDBOX is configured. See the docstring in "
        "backend/app/ehr/rpms_adapter.py for what a real RPMS interface would need."
    )
