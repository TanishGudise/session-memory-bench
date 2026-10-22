"""Settlement batches close at 17:00 UTC; payments after the cutoff settle the next day."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

CUTOFF_HOUR_UTC = 17


def cutoff_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, CUTOFF_HOUR_UTC).astimezone(timezone.utc)


def batch_for(paid_at: datetime) -> date:
    """Settlement day for a payment made at `paid_at` (an aware datetime)."""
    if paid_at.tzinfo is None:
        raise ValueError("paid_at must be timezone-aware")
    t = paid_at.astimezone(timezone.utc)
    day = t.date()
    return day + timedelta(days=1) if t >= cutoff_utc(day) else day


def settlement_report(payments: list[tuple[datetime, int]], day: date) -> dict:
    """Count and total of the payments that settle on `day`."""
    settled = [cents for paid_at, cents in payments if batch_for(paid_at) == day]
    return {"day": day, "count": len(settled), "total_cents": sum(settled)}
