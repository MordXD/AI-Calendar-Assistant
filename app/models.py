from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class StrictModel(BaseModel):
    """Base class enforcing consistent validation rules."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Attendee(StrictModel):
    email: str
    optional: bool = False


class Reminder(StrictModel):
    method: Literal["popup", "email"] = "popup"
    minutes_before: int = Field(default=15, ge=0)


class Recurrence(StrictModel):
    rrule: Optional[str] = None  # e.g., "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"


class EventDraft(StrictModel):
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    timezone: Optional[str] = None
    location: Optional[str] = None
    attendees: list[Attendee] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)
    recurrence: Optional[Recurrence] = None
    source: Optional[str] = None


class CalendarEvent(StrictModel):
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    timezone: str = "Europe/Riga"
    location: Optional[str] = None
    attendees: list[Attendee] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=lambda: [Reminder()])
    recurrence: Optional[Recurrence] = None
    source: Optional[str] = None  # free text (why this event exists)

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, value: datetime, info: ValidationInfo) -> datetime:
        start = info.data.get("start") if isinstance(info.data, dict) else None
        if isinstance(start, datetime) and value <= start:
            raise ValueError("end must be after start")
        return value


class SuggestionPayload(StrictModel):
    """Structured LLM response with candidate events."""

    candidates: list[EventDraft]


class SuggestEventsRequest(StrictModel):
    instruction: str
    now: Optional[datetime] = None
    timezone: str = "Europe/Riga"


class SuggestEventsResponse(StrictModel):
    candidates: list[CalendarEvent]
    trace_id: str


class CommitDecision(StrictModel):
    kind: Literal["create", "update", "skip"] = "create"
    reason: Optional[str] = None


class CommitPlanItem(StrictModel):
    event: CalendarEvent
    decision: CommitDecision


class CommitPlan(StrictModel):
    items: list[CommitPlanItem]
    trace_id: str


class CommitResult(StrictModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    trace_id: str
