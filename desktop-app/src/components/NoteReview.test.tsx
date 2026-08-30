import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DRAFT_BANNER } from "../api/client";
import { sampleNote } from "../test/sampleNote";
import {
  NEGATION_CHECK_LABEL,
  NEGATION_DISCLOSURE_TEXT,
  NoteReview,
} from "./NoteReview";

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

  it("labels assertion flags with the measured-reliability wording", () => {
    render(
      <NoteReview
        note={sampleNote({
          verification_needs: [
            { section: "subjective", sentence_index: 0, reason: "denied_by_patient" },
          ],
        })}
        saving={false}
        onSave={vi.fn()}
      />,
    );
    const flag = screen.getByText(NEGATION_CHECK_LABEL);
    expect(flag).toBeVisible();
    expect(flag).toHaveClass("verify-flag", "is-experimental");
    expect(screen.queryByText(/^Needs verification$/)).toBeNull();
    expect(screen.queryByText(/experimental — unreliable/)).toBeNull();
  });

  it("does not apply the experimental label to grounding flags", () => {
    render(
      <NoteReview
        note={sampleNote({
          subjective_grounding: { sources: [], directly_stated: false },
        })}
        saving={false}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("Sources unclear")).toBeVisible();
    expect(screen.queryByText(NEGATION_CHECK_LABEL)).toBeNull();
    expect(screen.queryByText(NEGATION_DISCLOSURE_TEXT)).toBeNull();
    expect(document.querySelector(".verify-flag")).toBeNull();
  });

  it("shows the negation disclosure once and hides it after dismiss", async () => {
    const user = userEvent.setup();
    const flagged = sampleNote({
      verification_needs: [
        { section: "subjective", sentence_index: 0, reason: "negation_or_question" },
      ],
    });
    const { unmount } = render(
      <NoteReview note={flagged} saving={false} onSave={vi.fn()} />,
    );
    expect(screen.getByRole("note")).toHaveTextContent(NEGATION_DISCLOSURE_TEXT);
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("note")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent(DRAFT_BANNER);

    unmount();
    render(<NoteReview note={flagged} saving={false} onSave={vi.fn()} />);
    expect(screen.queryByRole("note")).toBeNull();
    expect(screen.getByText(NEGATION_CHECK_LABEL)).toBeVisible();
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
