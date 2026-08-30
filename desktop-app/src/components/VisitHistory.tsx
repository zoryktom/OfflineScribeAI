import type { Visit } from "../api/client";
import { SyncStatusBadge } from "./SyncStatusBadge";

type Props = {
  visits: Visit[];
  selectedId: string | null;
  onSelect: (visit: Visit) => void;
};

function formatWhen(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function VisitHistory({ visits, selectedId, onSelect }: Props) {
  return (
    <section className="panel" aria-labelledby="history-heading">
      <p className="section-label">On this computer</p>
      <h2 id="history-heading">Visit history</h2>
      {visits.length === 0 ? (
        <p className="caption" style={{ marginTop: "0.75rem" }}>
          No visits yet. Record or upload one above.
        </p>
      ) : (
        <ul className="visit-list" style={{ marginTop: "0.75rem" }}>
          {visits.map((visit) => (
            <li key={visit.id}>
              <button
                type="button"
                className={
                  visit.id === selectedId ? "visit-item is-selected" : "visit-item"
                }
                onClick={() => onSelect(visit)}
              >
                <span>
                  <strong>{formatWhen(visit.timestamp)}</strong>
                  <span className="caption" style={{ display: "block" }}>
                    {visit.review_summary
                      ? visit.review_summary
                      : visit.provider_review?.reviewer_id
                        ? `Reviewed by ${visit.provider_review.reviewer_id}`
                        : "Draft"}
                  </span>
                </span>
                <SyncStatusBadge
                  status={visit.sync_status}
                  lastSyncError={visit.last_sync_error}
                  fhirPatientId={visit.fhir_patient_id}
                  fhirEncounterId={visit.fhir_encounter_id}
                />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
