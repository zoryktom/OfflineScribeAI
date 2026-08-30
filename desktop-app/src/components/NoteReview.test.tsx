import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DRAFT_BANNER } from "../api/client";
import { sampleNote } from "../test/sampleNote";
import { NoteReview } from "./NoteReview";

async function goToLastStep(user: ReturnType<typeof userEvent.setup>) {
  for (let index = 0; index < 5; index += 1) {
    await user.click(screen.getByRole("button", { name: "Continue" }));
  }
}

describe("NoteReview review gate", () => {
  it("shows a persistent draft banner with no dismiss control", () => {
    render(<NoteReview note={sampleNote()} saving={false} onSave={vi.fn()} />);
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent(DRAFT_BANNER);
    expect(banner.querySelector("button")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /dismiss|close|hide|got it/i }),
    ).toBeNull();
  });

  it("shows needs-verification when a SOAP section is flagged", () => {
    render(
      <NoteReview
        note={sampleNote({
          verification_needs: [
            { section: "subjective", sentence_index: 0, reason: "negation_or_question" },
          ],
        })}
        saving={false}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("Needs verification")).toBeVisible();
  });

  it("keeps Save disabled until a reviewer id is entered", async () => {
    const user = userEvent.setup();
    render(<NoteReview note={sampleNote()} saving={false} onSave={vi.fn()} />);
    await goToLastStep(user);
    const save = screen.getByRole("button", { name: "Save reviewed note" });
    expect(save).toBeDisabled();
    await user.type(screen.getByLabelText(/Reviewing provider id/i), "np-44");
    expect(save).toBeEnabled();
  });
});
