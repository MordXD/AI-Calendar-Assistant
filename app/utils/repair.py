from __future__ import annotations
from .time import DEFAULT_TZ
from app.models import CalendarEvent

# Простейшие авто‑ремонты: добавить TZ, увеличить длительность, если ≤ 0, и т.п.

def normalize_event(ev: CalendarEvent) -> CalendarEvent:
    if not ev.timezone:
        ev.timezone = DEFAULT_TZ
    # При необходимости можно расширить правила
    return ev