"""Encounter-to-signed-note event log. Local timing only."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class WorkflowEvent(BaseModel):
    encounter_id: str
    reviewer_id: str
    event: Literal[
        "open",
        "first_draft",
        "t_draft_ready",
        "t_first_edit",
        "edit",
        "t_sign",
        "sign",
        "reject",
    ]
    edit_type: str | None = None
    t_perf: float


class WorkflowSession:
    def __init__(self, encounter_id: str, reviewer_id: str) -> None:
        self.encounter_id = encounter_id
        self.reviewer_id = reviewer_id
        self.events: list[WorkflowEvent] = []
        self.mark("open")

    def mark(self, event: str, edit_type: str | None = None) -> WorkflowEvent:
        row = WorkflowEvent(
            encounter_id=self.encounter_id,
            reviewer_id=self.reviewer_id,
            event=event,  # type: ignore[arg-type]
            edit_type=edit_type,
            t_perf=time.perf_counter(),
        )
        self.events.append(row)
        return row

    def summary(self) -> dict[str, float | int | None]:
        times = {item.event: item.t_perf for item in self.events}
        first = times.get("first_draft")
        signed = times.get("sign")
        opened = times.get("open")
        return {
            "n_edits": sum(1 for item in self.events if item.event == "edit"),
            "time_to_first_draft": None if first is None or opened is None else first - opened,
            "time_to_sign": None if signed is None or opened is None else signed - opened,
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for item in self.events:
                handle.write(item.model_dump_json() + "\n")
