from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean
from time import perf_counter
from typing import List
from zoneinfo import ZoneInfo

from app.models import (
    CalendarEvent,
    CommitDecision,
    CommitPlan,
    CommitPlanItem,
    EventDraft,
    SuggestEventsRequest,
    SuggestionPayload,
)
from app.sgr import SGRController

_DEFAULT_TZ = "Europe/Riga"


def _build_event(offset_hours: int) -> EventDraft:
    tz = ZoneInfo(_DEFAULT_TZ)
    start = datetime(2025, 5, 20, 9 + offset_hours, 0, tzinfo=tz)
    return EventDraft(
        title=f"Focus block #{offset_hours + 1}",
        description="Benchmark generated block",
        start=start,
        end=start + timedelta(minutes=30),
        timezone=_DEFAULT_TZ,
    )


@dataclass(slots=True)
class BenchmarkLLM:
    payload: SuggestionPayload = field(
        default_factory=lambda: SuggestionPayload(
            candidates=[_build_event(i) for i in range(2)]
        )
    )

    def suggest_events(self, instruction: str, now_iso: str, timezone: str) -> SuggestionPayload:
        return self.payload


class BenchmarkCalendar:
    def __init__(self) -> None:
        self.created: List[CalendarEvent] = []
        tz = ZoneInfo(_DEFAULT_TZ)
        self._busy = [
            {
                "start": datetime(2025, 5, 20, 9, 0, tzinfo=tz).isoformat(),
                "end": datetime(2025, 5, 20, 10, 0, tzinfo=tz).isoformat(),
            }
        ]

    def create_event(self, ev: CalendarEvent) -> str:
        self.created.append(ev)
        return f"created-{len(self.created)}"

    def update_event(self, ev_id: str, ev: CalendarEvent) -> str:  # pragma: no cover - unused in bench
        return ev_id

    def list_between(self, time_min_iso: str, time_max_iso: str) -> list[dict]:
        return self._busy


def run(iterations: int = 250) -> None:
    controller = SGRController(llm=BenchmarkLLM(), calendar=BenchmarkCalendar())
    request = SuggestEventsRequest(instruction="Benchmark planning", timezone=_DEFAULT_TZ)

    timings: list[float] = []
    for _ in range(iterations):
        start = perf_counter()
        response = controller.suggest(request)
        plan = CommitPlan(
            items=[
                CommitPlanItem(event=event, decision=CommitDecision(kind="create"))
                for event in response.candidates
            ],
            trace_id=response.trace_id,
        )
        controller.commit(plan)
        timings.append(perf_counter() - start)

    total = sum(timings)
    print(f"Iterations: {iterations}")
    print(f"Total time: {total:.4f}s")
    print(f"Average per loop: {mean(timings)*1000:.2f} ms")
    print(f"Min/Max: {min(timings)*1000:.2f} ms / {max(timings)*1000:.2f} ms")


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    run()
