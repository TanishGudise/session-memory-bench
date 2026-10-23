from datetime import date, datetime, timezone

from billing.settlement import batch_for, cutoff_utc


def test_lesson_cutoff_unchanged():
    assert cutoff_utc(date(2026, 3, 2)) == datetime(2026, 3, 2, 17, 0, tzinfo=timezone.utc)
    assert batch_for(datetime(2026, 3, 2, 17, 0, tzinfo=timezone.utc)) == date(2026, 3, 3)
