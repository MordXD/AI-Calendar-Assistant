from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.models import (
    CalendarEvent,
    CommitPlan,
    CommitResult,
    SuggestEventsRequest,
    SuggestEventsResponse,
    SuggestionPayload,
)
from app.services.calendar_client import ICalendarClient
from app.services.google_calendar import GoogleCalendarClient
from app.services.llm_client import LLMClient, LLMUnavailableError
from app.utils.repair import normalize_event
from app.utils.time import now_in_tz

logger = logging.getLogger(__name__)


class SGRController:
    """Structured Generation & Repair loop orchestrator."""

    def __init__(
        self,
        *,
        llm: LLMClient | None = None,
        calendar: ICalendarClient | None = None,
    ) -> None:
        self.llm = llm or LLMClient()
        self.calendar = calendar or GoogleCalendarClient()

    # ------------------------------------------------------------------ Suggest
    def suggest(self, req: SuggestEventsRequest) -> SuggestEventsResponse:
        trace_id = str(uuid.uuid4())
        now_iso = (req.now or now_in_tz(req.timezone)).isoformat()

        try:
            payload = self.llm.suggest_events(req.instruction, now_iso, req.timezone)
        except LLMUnavailableError as exc:
            logger.warning("LLM unavailable, returning empty suggestions: %s", exc)
            payload = SuggestionPayload(candidates=[])

        candidates = [self._repair_candidate(ev, req.timezone) for ev in payload.candidates]
        return SuggestEventsResponse(candidates=candidates, trace_id=trace_id)

    # ------------------------------------------------------------------- Commit
    def commit(self, plan: CommitPlan) -> CommitResult:
        created = updated = skipped = 0
        errors: list[str] = []

        for item in plan.items:
            try:
                if item.decision.kind == "create":
                    self.calendar.create_event(item.event)
                    created += 1
                elif item.decision.kind == "update":
                    event_id = item.event.source or item.event.title
                    self.calendar.update_event(event_id, item.event)
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Commit error")
                errors.append(str(exc))

        return CommitResult(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            trace_id=plan.trace_id,
        )

    # ----------------------------------------------------------------- Internals
    def _repair_candidate(self, event: CalendarEvent, timezone: str) -> CalendarEvent:
        base = normalize_event(event, timezone=timezone)
        busy_slots = self._busy_slots(base)
        if busy_slots:
            base = normalize_event(base, timezone=base.timezone, existing_busy=busy_slots)
        return base

    def _busy_slots(self, event: CalendarEvent) -> list[tuple[datetime, datetime]]:
        if not event.start or not event.end:
            return []

        try:
            raw = self.calendar.list_between(event.start.isoformat(), event.end.isoformat())
        except Exception as exc:  # pragma: no cover - external API failure path
            logger.warning("Failed to fetch busy slots: %s", exc)
            return []

        tzinfo = event.start.tzinfo or event.end.tzinfo
        return [
            slot
            for slot in (
                self._parse_slot(item, tzinfo)
                for item in raw
            )
            if slot is not None
        ]

    @staticmethod
    def _parse_slot(
        payload: dict | None,
        tzinfo,
    ) -> tuple[datetime, datetime] | None:
        if not payload:
            return None

        start = _coerce_datetime(payload.get("start"), tzinfo)
        end = _coerce_datetime(payload.get("end"), tzinfo)
        if start and end:
            return start, end
        return None


def _coerce_datetime(value, tzinfo) -> datetime | None:
    if isinstance(value, dict):
        value = value.get("dateTime") or value.get("date")
    if isinstance(value, str):
        iso_value = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso_value)
        except ValueError:
            return None
        if dt.tzinfo is None and tzinfo is not None:
            dt = dt.replace(tzinfo=tzinfo)
        return dt
    return None
