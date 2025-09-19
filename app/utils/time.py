from __future__ import annotations
from datetime import datetime
import zoneinfo

DEFAULT_TZ = "Europe/Riga"

def now_in_tz(tz: str = DEFAULT_TZ) -> datetime:
    return datetime.now(tz=zoneinfo.ZoneInfo(tz))