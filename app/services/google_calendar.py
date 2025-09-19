from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.models import CalendarEvent, Reminder
from app.services.sqlite_store import CalendarSQLiteStore

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PROVIDER = "google_calendar"


def _read_possible_json(source: str) -> str | None:
    if not source:
        return None
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8")
    candidate = source.strip()
    if candidate.startswith("{") and candidate.endswith("}"):
        return candidate
    return None


class GoogleOAuthManager:
    """Handles OAuth credential lifecycle for Google Calendar."""

    def __init__(self, store: CalendarSQLiteStore) -> None:
        self._store = store

    def ensure_credentials(self, *, interactive: bool = False) -> Credentials | None:
        creds = self._load_credentials()
        if creds:
            return creds
        if interactive:
            return self._run_interactive_flow()
        return None

    def _load_credentials(self) -> Credentials | None:
        token_data = self._store.load_token(TOKEN_PROVIDER)
        if not token_data and settings.google_token_json:
            token_data = _read_possible_json(settings.google_token_json)
            if token_data:
                self._store.save_token(TOKEN_PROVIDER, token_data)
        if not token_data:
            return None
        try:
            info = json.loads(token_data)
            creds = Credentials.from_authorized_user_info(info, SCOPES)
        except Exception as exc:  # pragma: no cover - corrupted credentials
            logger.error("Failed to load Google credentials: %s", exc)
            return None

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._store.save_token(TOKEN_PROVIDER, creds.to_json())
            except Exception as exc:  # pragma: no cover - network refresh failure
                logger.warning("Failed to refresh Google token: %s", exc)
        return creds if creds and creds.valid else None

    def _run_interactive_flow(self) -> Credentials | None:
        client_config = self._load_client_config()
        if not client_config:
            logger.warning("Google OAuth config not provided; cannot run flow")
            return None
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)
        self._store.save_token(TOKEN_PROVIDER, creds.to_json())
        return creds

    @staticmethod
    def _load_client_config() -> dict[str, Any] | None:
        if settings.google_creds_json:
            raw = _read_possible_json(settings.google_creds_json)
            if raw:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Invalid GOOGLE_CREDS_JSON payload provided")
        if settings.google_client_id and settings.google_client_secret:
            redirect_uri = settings.google_redirect_uri or "http://localhost"
            return {
                "installed": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uris": [redirect_uri, "http://localhost"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
        return None


class GoogleCalendarClient:
    """Google Calendar client with SQLite persistence and optional OAuth."""

    def __init__(
        self,
        *,
        store: CalendarSQLiteStore | None = None,
        auth_manager: GoogleOAuthManager | None = None,
    ) -> None:
        self.calendar_id = settings.google_calendar_id
        self._store = store or CalendarSQLiteStore(settings.sqlite_db_path)
        self._auth = auth_manager or GoogleOAuthManager(self._store)
        self._service = None
        self._dry_run = True

        creds = self._auth.ensure_credentials()
        if creds:
            self._initialise_service(creds)
        else:
            logger.info(
                "Google Calendar client in dry-run mode; persisting data to %s",
                self._store.path,
            )

    # ----------------------------------------------------------------- helpers
    def _initialise_service(self, creds: Credentials) -> None:
        try:
            self._service = build(
                "calendar", "v3", credentials=creds, cache_discovery=False
            )
            self._dry_run = False
        except Exception as exc:  # pragma: no cover - API discovery errors
            logger.error("Failed to initialise Google Calendar service: %s", exc)
            self._service = None
            self._dry_run = True

    def authorize(self) -> bool:
        """Trigger interactive OAuth authorisation."""

        creds = self._auth.ensure_credentials(interactive=True)
        if not creds:
            return False
        self._initialise_service(creds)
        return not self._dry_run

    @property
    def dry_run(self) -> bool:
        return self._dry_run or self._service is None

    # ---------------------------------------------------------------- operations
    def create_event(self, ev: CalendarEvent) -> str:
        payload = self._to_google_payload(ev)
        event_id: str | None = None

        if not self.dry_run:
            try:
                created = (
                    self._service.events()
                    .insert(calendarId=self.calendar_id, body=payload)
                    .execute()
                )
                event_id = created.get("id")
                self._store.save_payload(event_id, created)
            except HttpError as exc:
                logger.error("Google API create_event error: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Unexpected Google API error during create_event")

        if not event_id:
            event_id = f"dry-run-{uuid4().hex}"
        self._store.save_calendar_event(event_id, ev)
        return event_id

    def update_event(self, ev_id: str, ev: CalendarEvent) -> str:
        payload = self._to_google_payload(ev)
        if not self.dry_run:
            try:
                self._service.events().update(
                    calendarId=self.calendar_id, eventId=ev_id, body=payload
                ).execute()
                self._store.save_payload(ev_id, payload)
            except HttpError as exc:
                logger.error("Google API update_event error: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Unexpected Google API error during update_event")
        self._store.save_calendar_event(ev_id, ev)
        return ev_id

    def list_between(self, time_min_iso: str, time_max_iso: str) -> list[dict]:
        if not self.dry_run:
            try:
                response = (
                    self._service.events()
                    .list(
                        calendarId=self.calendar_id,
                        timeMin=time_min_iso,
                        timeMax=time_max_iso,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
                items = response.get("items", [])
                for item in items:
                    self._store.save_payload(item.get("id"), item)
                return items
            except HttpError as exc:
                logger.error("Google API list_between error: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Unexpected Google API error during list_between")
        return self._store.list_between(time_min_iso, time_max_iso)

    # ----------------------------------------------------------------- internal
    @staticmethod
    def _to_google_payload(ev: CalendarEvent) -> dict[str, Any]:
        body: dict[str, Any] = {
            "summary": ev.title,
            "description": ev.description,
            "start": {
                "dateTime": ev.start.isoformat(),
                "timeZone": ev.timezone,
            },
            "end": {
                "dateTime": ev.end.isoformat(),
                "timeZone": ev.timezone,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {
                        "method": reminder.method,
                        "minutes": reminder.minutes_before,
                    }
                    for reminder in GoogleCalendarClient._unique_reminders(ev.reminders)
                ],
            },
        }
        if ev.location:
            body["location"] = ev.location
        if ev.attendees:
            body["attendees"] = [
                {"email": attendee.email, "optional": attendee.optional}
                for attendee in ev.attendees
            ]
        if ev.recurrence and ev.recurrence.rrule:
            body["recurrence"] = [ev.recurrence.rrule]
        if ev.source:
            body.setdefault("extendedProperties", {"private": {}})
            body["extendedProperties"]["private"]["source"] = ev.source
        return body

    @staticmethod
    def _unique_reminders(reminders: list[Reminder]) -> list[Reminder]:
        seen: set[tuple[str, int]] = set()
        result: list[Reminder] = []
        for reminder in reminders:
            key = (reminder.method, reminder.minutes_before)
            if key in seen:
                continue
            seen.add(key)
            result.append(reminder)
        return result


def _main() -> None:  # pragma: no cover - CLI helper
    parser = argparse.ArgumentParser(description="Google Calendar helper")
    parser.add_argument(
        "--authorize", action="store_true", help="Run the OAuth consent flow"
    )
    parser.add_argument(
        "--list", action="store_true", help="Print cached events from SQLite"
    )
    args = parser.parse_args()

    client = GoogleCalendarClient()
    if args.authorize:
        success = client.authorize()
        print("Authorization successful" if success else "Authorization failed")
    if args.list:
        for item in client._store.list_all():  # noqa: SLF001 - CLI utility
            print(json.dumps(item, indent=2, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover - CLI helper
    _main()

