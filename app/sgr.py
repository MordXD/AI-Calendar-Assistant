from __future__ import annotations
import logging
import uuid
from datetime import datetime
from typing import List

from app.models import (
    CalendarEvent,
    SuggestEventsRequest,
    SuggestEventsResponse,
    CommitPlan,
    CommitPlanItem,
    CommitDecision,
    CommitResult,
)
from app.services.llm_client import LLMClient
from app.services.google_calendar import GoogleCalendarClient
from app.utils.time import now_in_tz
from app.utils.repair import normalize_event

logger = logging.getLogger(__name__)

class SGRController:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.calendar = GoogleCalendarClient()

    # plan + parse + validate
    def suggest(self, req: SuggestEventsRequest) -> SuggestEventsResponse:
        trace_id = str(uuid.uuid4())
        now = (req.now or now_in_tz(req.timezone)).isoformat()
        raw = self.llm.suggest_events(req.instruction, now, req.timezone)
        # Ожидаем структуру вида {"candidates": [ ... ]}
        events: List[CalendarEvent] = []
        for item in raw.get("candidates", []):
            ev = CalendarEvent(**item)
            ev = normalize_event(ev)
            events.append(ev)
        return SuggestEventsResponse(candidates=events, trace_id=trace_id)

    # decide + commit
    def commit(self, plan: CommitPlan) -> CommitResult:
        created = updated = skipped = 0
        errors: List[str] = []
        for it in plan.items:
            try:
                if it.decision.kind == "create":
                    self.calendar.create_event(it.event)
                    created += 1
                elif it.decision.kind == "update":
                    # Требуется ev_id — для примера считаем, что в title содержится id (упрощение)
                    self.calendar.update_event(it.event.title, it.event)
                    updated += 1
                else:
                    skipped += 1
            except Exception as e:  # noqa
                logger.exception("Commit error")
                errors.append(str(e))
        return CommitResult(
            created=created, updated=updated, skipped=skipped, errors=errors, trace_id=plan.trace_id
        )