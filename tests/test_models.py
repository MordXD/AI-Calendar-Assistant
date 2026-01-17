from datetime import datetime, timedelta, timezone
import pytest
from models import CalendarEvent


def test_event_end_after_start():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        CalendarEvent(title="x", start=now, end=now)

    ok = CalendarEvent(title="x", start=now, end=now + timedelta(hours=1))
    assert ok.end > ok.start