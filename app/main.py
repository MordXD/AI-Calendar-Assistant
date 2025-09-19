from __future__ import annotations
import logging
from fastapi import FastAPI, Depends
from app.logging_conf import setup_logging
from app.config import settings
from app.models import (
    SuggestEventsRequest,
    SuggestEventsResponse,
    CommitPlan,
    CommitResult,
)
from app.deps import get_controller

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Calendar Assistant", version="0.1.0")

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.post("/events/suggest", response_model=SuggestEventsResponse)
def events_suggest(req: SuggestEventsRequest, ctrl = Depends(get_controller)):
    return ctrl.suggest(req)

@app.post("/events/sync", response_model=CommitResult)
def events_sync(plan: CommitPlan, ctrl = Depends(get_controller)):
    return ctrl.commit(plan)

# Заготовки для OAuth/вебхуков — реализация зависит от выбранного потока авторизации
@app.get("/auth/google/init")
def auth_google_init():
    return {"todo": "Redirect user to Google OAuth consent screen"}

@app.get("/auth/google/callback")
def auth_google_callback(code: str | None = None):
    return {"received_code": bool(code)}

@app.post("/webhook/google")
def webhook_google(body: dict):
    # TODO: обработать уведомления Google Calendar push
    return {"received": True}