from datetime import date, datetime, timedelta, timezone

import pytest

from billing.settlement import batch_for, cutoff_utc


def test_settlement_cutoff():
    day = date(2026, 3, 2)
    expected = datetime(2026, 3, 2, 17, 0).astimezone(timezone.utc)
    assert cutoff_utc(day) == expected


def test_batch_other_timezone():
    est = timezone(timedelta(hours=-5))
    paid = datetime(2026, 3, 2, 11, 30, tzinfo=est)  # 16:30 UTC
    assert batch_for(paid) == date(2026, 3, 2)


def test_batch_requires_aware_datetime():
    with pytest.raises(ValueError):
        batch_for(datetime(2026, 3, 2, 12, 0))
