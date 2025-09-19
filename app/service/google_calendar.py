from __future__ import annotations
import json
import logging
from typing import List
from datetime import datetime
from app.models import CalendarEvent
from app.config import settings

logger = logging.getLogger(__name__)

class GoogleCalendarClient:
    def __init__(self) -> None:
        self.calendar_id = settings.google_calendar_id
        self.creds_json = settings.google_creds_json
        self.token_json = settings.google_token_json
        # TODO: инициализация реального клиента Google API
        if not (self.creds_json or self.token_json):
            logger.warning("No Google credentials provided; using dry-run mode")
        self._dry_run = not (self.creds_json or self.token_json)

    def create_event(self, ev: CalendarEvent) -> str:
        if self._dry_run:
            logger.info("[DRY-RUN] create_event: %s", ev.model_dump())
            return "dry-run-id"
        # TODO: вставка в Google Calendar
        return "real-event-id"

    def update_event(self, ev_id: str, ev: CalendarEvent) -> str:
        if self._dry_run:
            logger.info("[DRY-RUN] update_event %s: %s", ev_id, ev.model_dump())
            return ev_id
        # TODO: обновление события
        return ev_id

    def list_between(self, time_min_iso: str, time_max_iso: str) -> List[dict]:
        if self._dry_run:
            logger.info("[DRY-RUN] list_between %s..%s", time_min_iso, time_max_iso)
            return []
        # TODO: выборка из Google Calendar
        return []