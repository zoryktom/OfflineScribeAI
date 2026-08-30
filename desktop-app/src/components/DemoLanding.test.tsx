import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DEMO_COVERAGE_BLURB, DEMO_LANDING_INTRO, DemoLanding } from "./DemoLanding";
import { DEMO_WATERMARK } from "./DemoWatermark";
import { NoteReview } from "./NoteReview";
import { TranscriptView } from "./TranscriptView";
import { sampleNote } from "../test/sampleNote";

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
