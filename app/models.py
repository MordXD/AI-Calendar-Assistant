from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class Attendee(BaseModel):
    email: str
    optional: bool = False

class Reminder(BaseModel):
    method: Literal["popup", "email"] = "popup"
    minutes_before: int = Field(15, ge=0)

class Recurrence(BaseModel):
    rrule: Optional[str] = None  # e.g., "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"

class CalendarEvent(BaseModel):
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    timezone: str = "Europe/Riga"
    location: Optional[str] = None
    attendees: List[Attendee] = []
    reminders: List[Reminder] = [Reminder()]
    recurrence: Optional[Recurrence] = None
    source: Optional[str] = None   # free text (why this event exists)

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v: datetime, values: dict):
        start = values.get("start")
        if start and v <= start:
            raise ValueError("end must be after start")
        return v

class SuggestEventsRequest(BaseModel):
    instruction: str
    now: Optional[datetime] = None
    timezone: str = "Europe/Riga"

class SuggestEventsResponse(BaseModel):
    candidates: list[CalendarEvent]
    trace_id: str

class CommitDecision(BaseModel):
    kind: Literal["create", "update", "skip"] = "create"
    reason: Optional[str] = None

class CommitPlanItem(BaseModel):
    event: CalendarEvent
    decision: CommitDecision

class CommitPlan(BaseModel):
    items: list[CommitPlanItem]
    trace_id: str

class CommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = []
    trace_id: str