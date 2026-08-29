const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const API_KEY = import.meta.env.VITE_LOCAL_API_KEY ?? "";

export type SyncStatus = "pending" | "synced" | "failed";

export type SuggestedIcd10 = {
  code: string;
  description: string;
  accepted: boolean | null;
};

export type FollowUpItem = {
  text: string;
  timeframe: string | null;
};

export type NoteSource = {
  start_s: number;
  end_s: number;
  text: string;
};

export type GroundedSection = {
  sources: NoteSource[];
  directly_stated: boolean;
};

export type Note = {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  suggested_icd10: SuggestedIcd10[];
  follow_up: FollowUpItem[];
  subjective_grounding?: GroundedSection;
  objective_grounding?: GroundedSection;
  assessment_grounding?: GroundedSection;
  plan_grounding?: GroundedSection;
};

export type SpeakerTurn = {
  speaker: "provider" | "patient" | "unknown";
  start_s: number;
  end_s: number;
  text: string;
};

export type Visit = {
  id: string;
  timestamp: string;
  transcript: string;
  transcript_segments: SpeakerTurn[];
  note: Note;
  sync_status: SyncStatus;
  fhir_resource_id: string | null;
  edited_by_provider: boolean;
  fhir_patient_id: string | null;
  fhir_encounter_id: string | null;
  last_sync_error: string | null;
};

export type HealthResponse = {
  status: string;
  stub_mode: boolean;
  ollama_model: string;
};

export type SyncRunResult = {
  dry_run: boolean;
  results: Array<{
    visit_id: string;
    sync_status: SyncStatus;
    fhir_resource_id: string | null;
    dry_run: boolean;
    error: string | null;
  }>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (API_KEY) {
    headers.set("X-API-Key", API_KEY);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Keep the generic status message when the body is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function listVisits(): Promise<Visit[]> {
  return request<Visit[]>("/visits");
}

export function getVisit(id: string): Promise<Visit> {
  return request<Visit>(`/visits/${id}`);
}

export async function createVisitFromAudio(file: File): Promise<Visit> {
  const body = new FormData();
  body.append("audio", file);
  return request<Visit>("/visits", { method: "POST", body });
}

export function updateVisitNote(id: string, note: Note): Promise<Visit> {
  return request<Visit>(`/visits/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note, edited_by_provider: true }),
  });
}

export function runSync(dryRun = true): Promise<SyncRunResult> {
  const query = dryRun ? "?dry_run=true" : "";
  return request<SyncRunResult>(`/sync${query}`, { method: "POST" });
}
