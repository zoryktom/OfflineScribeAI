import type { Note } from "../api/client";

export function sampleNote(overrides: Partial<Note> = {}): Note {
  return {
    subjective: "Cough for three days.",
    objective: "Not documented in visit.",
    assessment: "Possible viral illness.",
    plan: "Supportive care.",
    suggested_icd10: [
      { code: "R05.9", description: "Cough, unspecified", accepted: null },
    ],
    follow_up: [{ text: "Return if worse", timeframe: "48 hours" }],
    verification_needs: [],
    ...overrides,
  };
}
