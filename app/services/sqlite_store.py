from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import CalendarEvent


def _ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _iso_to_timestamp(value: str) -> float:
    iso_value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso_value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _coerce_iso(payload: Any) -> str | None:
    if isinstance(payload, dict):
        candidate = payload.get("dateTime") or payload.get("date")
        if isinstance(candidate, str):
            return candidate
        return None
    if isinstance(payload, str):
        return payload
    return None


class CalendarSQLiteStore:
    """Simple persistence layer for Google Calendar artefacts."""

    def __init__(self, db_path: str) -> None:
        self.path = Path(db_path)
        _ensure_parent(self.path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ------------------------------------------------------------------ tokens
    def save_token(self, provider: str, data: str) -> None:
        with self._conn:
            self._conn.execute(
                (
                    "INSERT INTO tokens(provider, data, updated_at) "
                    "VALUES(?, ?, CURRENT_TIMESTAMP) "
                    "ON CONFLICT(provider) DO UPDATE SET "
                    "data=excluded.data, updated_at=CURRENT_TIMESTAMP"
                ),
                (provider, data),
            )

    def load_token(self, provider: str) -> str | None:
        cur = self._conn.execute(
            "SELECT data FROM tokens WHERE provider = ?", (provider,)
        )
        row = cur.fetchone()
        return row["data"] if row else None

    # ------------------------------------------------------------------ events
    def save_calendar_event(self, event_id: str, event: CalendarEvent) -> None:
        payload = event.model_dump(mode="json")
        payload.setdefault("id", event_id)
        self._persist_payload(
            event_id,
            title=event.title,
            start_iso=event.start.isoformat(),
            end_iso=event.end.isoformat(),
            payload=payload,
        )

    def save_payload(self, event_id: str | None, payload: dict[str, Any]) -> None:
        event_id = event_id or f"payload-{uuid4().hex}"
        start_iso = _coerce_iso(payload.get("start"))
        end_iso = _coerce_iso(payload.get("end"))
        if not (start_iso and end_iso):
            return
        title = (
            payload.get("summary")
            or payload.get("title")
            or payload.get("description")
            or event_id
        )
        payload = dict(payload)
        payload.setdefault("id", event_id)
        self._persist_payload(event_id, title, start_iso, end_iso, payload)

    def list_between(self, time_min_iso: str, time_max_iso: str) -> list[dict[str, Any]]:
        start_ts = _iso_to_timestamp(time_min_iso.replace("Z", "+00:00"))
        end_ts = _iso_to_timestamp(time_max_iso.replace("Z", "+00:00"))
        cur = self._conn.execute(
            (
                "SELECT payload_json FROM events "
                "WHERE start_ts < ? AND end_ts > ? "
                "ORDER BY start_ts"
            ),
            (end_ts, start_ts),
        )
        return [json.loads(row["payload_json"]) for row in cur.fetchall()]

    def list_all(self) -> list[dict[str, Any]]:
        cur = self._conn.execute("SELECT payload_json FROM events ORDER BY start_ts")
        return [json.loads(row["payload_json"]) for row in cur.fetchall()]

    # -------------------------------------------------------------------- utils
    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            self.close()
        except Exception:
            pass

    def _ensure_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tokens (
                    provider TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start_iso TEXT NOT NULL,
                    end_iso TEXT NOT NULL,
                    start_ts REAL NOT NULL,
                    end_ts REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _persist_payload(
        self,
        event_id: str,
        title: str,
        start_iso: str,
        end_iso: str,
        payload: dict[str, Any],
    ) -> None:
        start_ts = _iso_to_timestamp(start_iso)
        end_ts = _iso_to_timestamp(end_iso)
        with self._conn:
            self._conn.execute(
                (
                    "INSERT INTO events(event_id, title, start_iso, end_iso, start_ts, end_ts, payload_json, updated_at) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
                    "ON CONFLICT(event_id) DO UPDATE SET "
                    "title=excluded.title, start_iso=excluded.start_iso, end_iso=excluded.end_iso, "
                    "start_ts=excluded.start_ts, end_ts=excluded.end_ts, payload_json=excluded.payload_json, "
                    "updated_at=CURRENT_TIMESTAMP"
                ),
                (
                    event_id,
                    title,
                    start_iso,
                    end_iso,
                    start_ts,
                    end_ts,
                    json.dumps(payload, default=str),
                ),
            )

