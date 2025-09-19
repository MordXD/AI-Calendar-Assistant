from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Sequence, Union

import zoneinfo
from zoneinfo import ZoneInfoNotFoundError

from app.models import Attendee, CalendarEvent, EventDraft, Reminder, Recurrence
from app.utils.time import DEFAULT_TZ

DEFAULT_EVENT_DURATION = timedelta(hours=1)
CONFLICT_SHIFT = timedelta(minutes=15)
MAX_SHIFT_ATTEMPTS = 8

EventLike = Union[CalendarEvent, EventDraft]


def normalize_event(
    event: EventLike,
    *,
    timezone: str | None = None,
    existing_busy: Sequence[tuple[datetime, datetime]] | None = None,
) -> CalendarEvent:
    """Apply SGR repair policies to keep events consistent."""

    draft = event.model_copy(deep=True)
    tz_name = timezone or getattr(draft, "timezone", None) or DEFAULT_TZ
    setattr(draft, "timezone", tz_name)

    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo(DEFAULT_TZ)
        setattr(draft, "timezone", DEFAULT_TZ)

    start = _ensure_timezone(getattr(draft, "start"), tz)
    end = _ensure_timezone(getattr(draft, "end"), tz)
    if end <= start:
        end = start + DEFAULT_EVENT_DURATION

    attendees = [
        attendee
        if isinstance(attendee, Attendee)
        else Attendee.model_validate(attendee)
        for attendee in getattr(draft, "attendees", [])
    ]

    reminders = [
        reminder
        if isinstance(reminder, Reminder)
        else Reminder.model_validate(reminder)
        for reminder in getattr(draft, "reminders", [])
    ] or [Reminder()]

    recurrence = getattr(draft, "recurrence", None)
    if recurrence and not isinstance(recurrence, Recurrence):
        recurrence = Recurrence.model_validate(recurrence)

    normalized = CalendarEvent(
        title=getattr(draft, "title"),
        description=getattr(draft, "description", None),
        start=start,
        end=end,
        timezone=getattr(draft, "timezone"),
        location=getattr(draft, "location", None),
        attendees=attendees,
        reminders=reminders,
        recurrence=recurrence,
        source=getattr(draft, "source", None),
    )

    busy_slots = list(existing_busy or ())
    if busy_slots:
        normalized = _shift_to_free_slot(normalized, busy_slots)

    return normalized


def _ensure_timezone(dt: datetime, tz: zoneinfo.ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _shift_to_free_slot(event: CalendarEvent, busy_slots: Sequence[tuple[datetime, datetime]]) -> CalendarEvent:
    ev = event.model_copy(deep=True)
    for _ in range(MAX_SHIFT_ATTEMPTS):
        if not _has_conflict(ev.start, ev.end, busy_slots):
            return ev
        ev.start += CONFLICT_SHIFT
        ev.end += CONFLICT_SHIFT
    return ev


def _has_conflict(
    start: datetime,
    end: datetime,
    busy_slots: Iterable[tuple[datetime, datetime]],
) -> bool:
    for busy_start, busy_end in busy_slots:
        if start < busy_end and end > busy_start:
            return True
    return False
