from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from models import CalendarEvent, Reminder
from services.google_calendar import GoogleCalendarClient
from services.sqlite_store import CalendarSQLiteStore


def _sample_event() -> CalendarEvent:
    start = datetime(2025, 5, 20, 9, 0, tzinfo=ZoneInfo("UTC"))
    end = start + timedelta(hours=1)
    return CalendarEvent(
        title="Daily standup",
        description="sync",
        start=start,
        end=end,
        timezone="UTC",
        reminders=[Reminder(method="popup", minutes_before=10)],
    )


def test_sqlite_store_roundtrip(tmp_path) -> None:
    store = CalendarSQLiteStore(str(tmp_path / "calendar.db"))
    event = _sample_event()
    store.save_calendar_event("evt-1", event)
    events = store.list_between(
        (event.start - timedelta(minutes=30)).isoformat(),
        (event.end + timedelta(minutes=30)).isoformat(),
    )
    assert events
    assert events[0]["title"] == "Daily standup"
    assert events[0]["id"] == "evt-1"


def test_google_client_dry_run_persists(tmp_path) -> None:
    store = CalendarSQLiteStore(str(tmp_path / "calendar.db"))
    client = GoogleCalendarClient(store=store)

    assert client.dry_run

    event = _sample_event()
    event_id = client.create_event(event)

    assert event_id.startswith("dry-run-") or event_id == "dry-run-id"

    listings = client.list_between(
        (event.start - timedelta(minutes=30)).isoformat(),
        (event.end + timedelta(minutes=30)).isoformat(),
    )
    assert listings
    assert any(item.get("title") == "Daily standup" for item in listings)


def test_store_token_roundtrip(tmp_path) -> None:
    store = CalendarSQLiteStore(str(tmp_path / "calendar.db"))
    store.save_token("google", "{\"token\": \"value\"}")
    assert store.load_token("google") == "{\"token\": \"value\"}"
