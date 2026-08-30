import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TranscriptView } from "./TranscriptView";

describe("TranscriptView ASR flags", () => {
  it("renders unusual medication tokens as visible warnings", () => {
    render(
      <TranscriptView
        transcript="I still take the liz in April 10 mg."
        segments={[
          {
            speaker: "unknown",
            start_s: 5,
            end_s: 9,
            text: "I still take the liz in April 10 mg.",
          },
        ]}
        asrFlags={[
          {
            start_s: 5,
            end_s: 9,
            text: "liz",
            reason: "unusual_medication_token",
          },
        ]}
      />,
    );
    expect(screen.getByText(/Check “liz”/)).toBeVisible();
    expect(screen.getByText(/unusual medication token/)).toBeVisible();
  });
});
