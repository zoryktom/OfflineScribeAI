import { useCallback, useEffect, useState } from "react";

import {
  DRAFT_BANNER,
  createVisitFromAudio,
  exportVisitText,
  getHealth,
  listVisits,
  loadDemoEncounter,
  runSync,
  updateVisitNote,
  type HealthResponse,
  type Note,
  type ReviewAction,
  type Visit,
} from "./api/client";
import { DemoLanding } from "./components/DemoLanding";
import { DemoWalkthrough } from "./components/DemoWalkthrough";
import { DEMO_WATERMARK, DemoWatermark } from "./components/DemoWatermark";
import { NoteReview } from "./components/NoteReview";
import { RecordOrUpload } from "./components/RecordOrUpload";
import { SyncStatusBadge } from "./components/SyncStatusBadge";
import { TranscriptView } from "./components/TranscriptView";
import { DEMO_SYNC_DISABLED, VisitHistory } from "./components/VisitHistory";

export const CONFIG_CHECK_LABEL = "Checking configuration…";

const WALKTHROUGH_SCRIPT = "synthetic_clinic_visit_dialogue.txt";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [selected, setSelected] = useState<Visit | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [walkthroughStep, setWalkthroughStep] = useState(0);
  const [startedDemo, setStartedDemo] = useState(false);

  const healthReady = health !== null;
  const demoMode = health?.demo_mode === true;
  const showRealTools = health?.demo_mode === false;
  const watermark = demoMode ? DEMO_WATERMARK : null;

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

  async function handleSave(note: Note, reviewerId: string, actions: ReviewAction[]) {
    if (!selected) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await updateVisitNote(selected.id, note, reviewerId, actions);
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

  async function handleStartDemo() {
    setBusy(true);
    setError(null);
    try {
      const visit = await loadDemoEncounter(WALKTHROUGH_SCRIPT);
      const next = await refresh();
      setSelected(next.find((item) => item.id === visit.id) ?? visit);
      setStartedDemo(true);
      setWalkthroughStep(0);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load the fake visit. Confirm DEMO_MODE=true and the local server is running.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDemoExport() {
    if (!selected) {
      return;
    }
    try {
      const payload = await exportVisitText(selected.id);
      const blob = new Blob([payload.text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${selected.id}.txt`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not export the demo note.");
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <p className="app-kicker">
          {!healthReady
            ? CONFIG_CHECK_LABEL
            : demoMode
              ? "Synthetic demo only"
              : "Workflow review workstation"}
        </p>
        <h1>Offline Scribe</h1>
        {demoMode ? <DemoWatermark /> : null}
        {healthReady ? (
          <p className="app-lede">
            {demoMode
              ? "A locked-down look at the documentation workflow on a fake conversation: draft, flags, and named review."
              : "Record a visit, do the review work the draft cannot, and keep it on this computer until you choose to sync."}
          </p>
        ) : null}
        {health?.stub_mode && showRealTools ? (
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

      {!healthReady && !error ? (
        <p className="caption" role="status">
          {CONFIG_CHECK_LABEL}
        </p>
      ) : null}

      {demoMode && !startedDemo ? (
        <DemoLanding onStart={() => void handleStartDemo()} starting={busy} />
      ) : null}

      {demoMode && startedDemo ? (
        <DemoWalkthrough
          step={walkthroughStep}
          onNext={() => setWalkthroughStep((value) => Math.min(3, value + 1))}
        />
      ) : null}

      {showRealTools ? <RecordOrUpload busy={busy} onSubmit={handleUpload} /> : null}

      {selected && (!demoMode || startedDemo) ? (
        <>
          <div className="panel">
            <p className="section-label">This visit</p>
            {watermark ? <DemoWatermark /> : null}
            <p className="caption">{selected.id}</p>
            {showRealTools ? (
              <SyncStatusBadge
                status={selected.sync_status}
                lastSyncError={selected.last_sync_error}
                fhirPatientId={selected.fhir_patient_id}
                fhirEncounterId={selected.fhir_encounter_id}
              />
            ) : (
              <p className="caption">{DEMO_SYNC_DISABLED}</p>
            )}
            {selected.review_summary ? (
              <p className="caption review-summary">{selected.review_summary}</p>
            ) : null}
            {demoMode ? (
              <div className="row" style={{ marginTop: "0.85rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void handleDemoExport()}
                >
                  Download watermarked demo note
                </button>
              </div>
            ) : null}
          </div>
          <p className="draft-banner" role="status">
            {DRAFT_BANNER}
          </p>
          <TranscriptView
            transcript={selected.transcript}
            segments={selected.transcript_segments ?? []}
            asrFlags={selected.asr_flags ?? []}
            watermark={selected.watermark ?? watermark}
          />
          <NoteReview
            key={selected.id + (selected.provider_review?.reviewed_at ?? "draft")}
            note={selected.note}
            saving={saving}
            onSave={handleSave}
            watermark={selected.watermark ?? watermark}
          />
        </>
      ) : null}

      {healthReady && (!demoMode || startedDemo) ? (
        <VisitHistory
          visits={visits}
          selectedId={selected?.id ?? null}
          onSelect={setSelected}
          demoMode={demoMode}
        />
      ) : null}

      {demoMode ? (
        <p className="caption">
          Chart preview and FHIR dry-run are unavailable in demo mode.
        </p>
      ) : showRealTools ? (
        <p className="caption">
          EHR sync is opt-in.{" "}
          <button type="button" className="btn btn-secondary" onClick={() => void handleDryRun()}>
            Preview FHIR JSON (dry-run)
          </button>
        </p>
      ) : null}
    </div>
  );
}
