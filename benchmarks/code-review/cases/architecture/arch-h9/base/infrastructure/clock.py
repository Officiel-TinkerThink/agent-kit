from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def today(self) -> date: ...


class SystemClock:
    def today(self) -> date:
        return datetime.now(timezone.utc).date()


def today_utc() -> date:
    return datetime.now(timezone.utc).date()
