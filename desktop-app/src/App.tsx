import { useCallback, useEffect, useState } from "react";

import {
  createVisitFromAudio,
  getHealth,
  listVisits,
  runSync,
  updateVisitNote,
  type HealthResponse,
  type Note,
  type Visit,
} from "./api/client";
import { NoteReview } from "./components/NoteReview";
import { RecordOrUpload } from "./components/RecordOrUpload";
import { SyncStatusBadge } from "./components/SyncStatusBadge";
import { TranscriptView } from "./components/TranscriptView";
import { VisitHistory } from "./components/VisitHistory";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [selected, setSelected] = useState<Visit | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextHealth, nextVisits] = await Promise.all([getHealth(), listVisits()]);
    setHealth(nextHealth);
    setVisits(nextVisits);
    return nextVisits;
  }, []);

  useEffect(() => {
    void refresh().catch((reason: unknown) => {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not reach the local Offline Scribe server. Start it with uvicorn on port 8000.",
      );
    });
  }, [refresh]);

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const visit = await createVisitFromAudio(file);
      const next = await refresh();
      setSelected(next.find((item) => item.id === visit.id) ?? visit);
      setMessage("Draft note is ready to review. Nothing has been sent to an EHR.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not create the visit. Confirm the local server is running.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSave(note: Note) {
    if (!selected) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await updateVisitNote(selected.id, note);
      setSelected(updated);
      await refresh();
      setMessage("Reviewed note saved on this computer.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not save the reviewed note.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDryRun() {
    setError(null);
    try {
      const result = await runSync(true);
      const count = result.results.length;
      setMessage(
        count === 0
          ? "No pending visits to preview."
          : `Dry-run built FHIR JSON for ${count} pending visit${count === 1 ? "" : "s"} (printed in the server terminal). Nothing was sent.`,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Dry-run sync failed.");
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <p className="app-kicker">Rural clinic workstation</p>
        <h1>Offline Scribe</h1>
        <p className="app-lede">
          Record a visit, review the SOAP note, and keep it on this computer until
          you choose to sync.
        </p>
        {health?.stub_mode ? (
          <p className="stub-note">
            STUB_MODE is on: SOAP notes are canned sample text so the app can
            run without Ollama. Transcription still uses on-device faster-whisper.
            Set STUB_MODE=false in backend/.env to draft notes with the local model.
          </p>
        ) : null}
      </header>

      {error ? (
        <p className="banner is-error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="banner">{message}</p> : null}

      <RecordOrUpload busy={busy} onSubmit={handleUpload} />

      {selected ? (
        <>
          <div className="panel">
            <p className="section-label">This visit</p>
            <SyncStatusBadge
              status={selected.sync_status}
              lastSyncError={selected.last_sync_error}
              fhirPatientId={selected.fhir_patient_id}
              fhirEncounterId={selected.fhir_encounter_id}
            />
          </div>
          <TranscriptView
            transcript={selected.transcript}
            segments={selected.transcript_segments ?? []}
          />
          <NoteReview
            key={selected.id + String(selected.edited_by_provider)}
            note={selected.note}
            saving={saving}
            onSave={handleSave}
          />
        </>
      ) : null}

      <VisitHistory
        visits={visits}
        selectedId={selected?.id ?? null}
        onSelect={setSelected}
      />

      <p className="caption">
        EHR sync is opt-in.{" "}
        <button type="button" className="btn btn-secondary" onClick={() => void handleDryRun()}>
          Preview FHIR JSON (dry-run)
        </button>
      </p>
    </div>
  );
}
