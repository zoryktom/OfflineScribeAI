import type { SyncStatus } from "../api/client";

type Props = {
  status: SyncStatus;
  lastSyncError?: string | null;
  fhirPatientId?: string | null;
  fhirEncounterId?: string | null;
};

function CloudIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12.4 7.1A3.5 3.5 0 0 0 6 5.8 3 3 0 0 0 3 11h9.2A2.8 2.8 0 0 0 12.4 7.1Z"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M6.4 11.2 3.2 8l1.1-1.1 2.1 2.1 5.2-5.2L12.7 5z"
      />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M8 1.5 1.5 13h13L8 1.5Zm.8 9.2H7.2V12h1.6v-1.3Zm0-4.4H7.2v3.2h1.6V6.3Z"
      />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M6.2 9.8a3 3 0 0 1 0-4.2l1.8-1.8a3 3 0 0 1 4.2 4.2L11 9.2M9.8 6.2a3 3 0 0 1 0 4.2L8 12.2a3 3 0 1 1-4.2-4.2L5 6.8"
      />
    </svg>
  );
}

export function SyncStatusBadge({
  status,
  lastSyncError,
  fhirPatientId,
  fhirEncounterId,
}: Props) {
  const missingChartLink = !fhirPatientId || !fhirEncounterId;
  const failed = status === "failed" || Boolean(lastSyncError);
  const synced = status === "synced";

  if (synced) {
    return (
      <span className="status-badge is-synced">
        <CheckIcon />
        Sent to the health record
      </span>
    );
  }

  if (missingChartLink) {
    return (
      <span className="status-badge is-unlinked">
        <LinkIcon />
        Missing patient link — cannot sync
      </span>
    );
  }

  if (failed) {
    return (
      <span className="status-badge is-failed">
        <AlertIcon />
        <span>
          Last sync did not go through
          {lastSyncError ? (
            <span className="status-error">{lastSyncError}</span>
          ) : null}
        </span>
      </span>
    );
  }

  return (
    <span className="status-badge">
      <CloudIcon />
      Saved, will sync when online
    </span>
  );
}
