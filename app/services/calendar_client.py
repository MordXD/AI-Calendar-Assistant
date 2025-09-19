from __future__ import annotations
from typing import Protocol

from app.models import CalendarEvent


class ICalendarClient(Protocol):
    """Protocol describing calendar operations used by the controller."""

    def create_event(self, ev: CalendarEvent) -> str: ...

    def update_event(self, ev_id: str, ev: CalendarEvent) -> str: ...

    def list_between(self, time_min_iso: str, time_max_iso: str) -> list[dict]: ...
