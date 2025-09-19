from __future__ import annotations

from datetime import datetime
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


class StubLLM:
    def __init__(self) -> None:
        self.payload = SuggestionPayload(
            candidates=[
                EventDraft(
                    title="Deep Work",
                    description="Focus session",
                    start=datetime(2025, 5, 20, 9, 0, 0),  # naive on purpose
                    end=datetime(2025, 5, 20, 9, 0, 0),
                    timezone="",
                    reminders=[],
                )
            ]
        )

    def suggest_events(self, instruction: str, now_iso: str, timezone: str) -> SuggestionPayload:
        return self.payload


class StubCalendar:
    def __init__(self) -> None:
        self.created: list[CalendarEvent] = []
        self.updated: list[tuple[str, CalendarEvent]] = []
        base_tz = ZoneInfo("Europe/Riga")
        self.busy_payload = [
            {
                "start": (datetime(2025, 5, 20, 9, 0, tzinfo=base_tz).isoformat()),
                "end": (datetime(2025, 5, 20, 10, 0, tzinfo=base_tz).isoformat()),
            }
        ]

    def create_event(self, ev: CalendarEvent) -> str:
        self.created.append(ev)
        return "created-id"

    def update_event(self, ev_id: str, ev: CalendarEvent) -> str:
        self.updated.append((ev_id, ev))
        return ev_id

    def list_between(self, time_min_iso: str, time_max_iso: str) -> list[dict]:
        return self.busy_payload


def test_suggest_applies_repair_and_conflict_resolution() -> None:
    controller = SGRController(llm=StubLLM(), calendar=StubCalendar())
    request = SuggestEventsRequest(instruction="schedule focus", timezone="Europe/Riga")

    response = controller.suggest(request)

    assert response.trace_id
    assert len(response.candidates) == 1
    event = response.candidates[0]
    assert event.timezone == "Europe/Riga"
    assert event.end > event.start
    assert event.reminders  # default reminder added
    assert event.start.hour == 10  # shifted to avoid conflict at 9:00


def test_commit_counts_operations() -> None:
    calendar = StubCalendar()
    controller = SGRController(llm=StubLLM(), calendar=calendar)
    response = controller.suggest(SuggestEventsRequest(instruction="schedule", timezone="Europe/Riga"))
    plan = CommitPlan(
        items=[
            CommitPlanItem(event=response.candidates[0], decision=CommitDecision(kind="create")),
            CommitPlanItem(event=response.candidates[0], decision=CommitDecision(kind="skip")),
        ],
        trace_id=response.trace_id,
    )

    result = controller.commit(plan)

    assert result.created == 1
    assert result.skipped == 1
    assert result.updated == 0
    assert result.errors == []
    assert calendar.created  # ensure call went through
