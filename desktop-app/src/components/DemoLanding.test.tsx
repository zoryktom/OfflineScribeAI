import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DEMO_COVERAGE_BLURB, DEMO_LANDING_INTRO, DemoLanding } from "./DemoLanding";
import { DemoWalkthrough } from "./DemoWalkthrough";
import { DEMO_WATERMARK } from "./DemoWatermark";
import { NoteReview } from "./NoteReview";
import { TranscriptView } from "./TranscriptView";
import { DEMO_SYNC_DISABLED, VisitHistory } from "./VisitHistory";
import { sampleNote } from "../test/sampleNote";
import type { Visit } from "../api/client";

describe("demo landing and watermarks", () => {
  it("explains the fake-patient limit and measured misses before a note is shown", () => {
    render(<DemoLanding onStart={vi.fn()} starting={false} />);
    expect(screen.getByText(DEMO_LANDING_INTRO)).toBeVisible();
    expect(screen.getByText(DEMO_COVERAGE_BLURB)).toBeVisible();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("starts the walkthrough from the landing button", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    render(<DemoLanding onStart={onStart} starting={false} />);
    await user.click(screen.getByRole("button", { name: /Start the fake visit walkthrough/i }));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("shows the non-removable watermark on transcript and note views", () => {
    render(
      <TranscriptView
        transcript="fake talk"
        watermark={DEMO_WATERMARK}
      />,
    );
    expect(screen.getByTestId("demo-watermark")).toHaveTextContent(DEMO_WATERMARK);
    expect(
      screen.queryByRole("button", { name: /dismiss|close|hide/i }),
    ).toBeNull();
  });

  it("reuses the onboarding coverage numbers on walkthrough step 3", () => {
    render(<DemoWalkthrough step={2} onNext={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Flags" })).toBeVisible();
    expect(
      screen.getByText((text) => text.includes(DEMO_COVERAGE_BLURB)),
    ).toBeVisible();
    expect(screen.queryByText(/planted errors were often missed/i)).toBeNull();
  });

  it("does not raise a missing-patient-link warning in demo visit history", () => {
    const visit: Visit = {
      id: "DEMO-1",
      timestamp: "2026-08-30T21:00:00.000Z",
      transcript: "fake talk",
      transcript_segments: [],
      note: sampleNote(),
      sync_status: "pending",
      fhir_resource_id: null,
      provider_review: null,
      asr_flags: [],
      fhir_patient_id: null,
      fhir_encounter_id: null,
      last_sync_error: null,
      review_summary: null,
      watermark: DEMO_WATERMARK,
    };
    render(
      <VisitHistory
        visits={[visit]}
        selectedId={visit.id}
        onSelect={vi.fn()}
        demoMode
      />,
    );
    expect(screen.getByText(DEMO_SYNC_DISABLED)).toBeVisible();
    expect(screen.queryByText(/Missing patient link/i)).toBeNull();
  });

  it("shows the watermark on the SOAP review panel", () => {
    render(
      <NoteReview
        note={sampleNote()}
        saving={false}
        onSave={vi.fn()}
        watermark={DEMO_WATERMARK}
      />,
    );
    expect(screen.getAllByTestId("demo-watermark")[0]).toHaveTextContent(DEMO_WATERMARK);
  });
});
