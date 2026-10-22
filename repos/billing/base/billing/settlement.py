"""Settlement batches close at 17:00 UTC; payments after the cutoff settle the next day."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

CUTOFF_HOUR_UTC = 17


def cutoff_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, CUTOFF_HOUR_UTC, tzinfo=timezone.utc)


def batch_for(paid_at: datetime) -> date:
    """Settlement day for a payment made at `paid_at` (an aware datetime)."""
    if paid_at.tzinfo is None:
        raise ValueError("paid_at must be timezone-aware")
    t = paid_at.astimezone(timezone.utc)
    day = t.date()
    return day + timedelta(days=1) if t >= cutoff_utc(day) else day
