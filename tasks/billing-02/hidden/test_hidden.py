from datetime import date, datetime, timedelta, timezone

from billing.settlement import CUTOFF_HOUR_UTC, batch_for, cutoff_utc, settlement_report

UTC = timezone.utc
PST = timezone(timedelta(hours=-8))


def test_func_report_counts_payments_by_settlement_day():
    payments = [
        (datetime(2026, 3, 1, 17, 0, tzinfo=UTC), 100),   # after Mar 1 cutoff -> Mar 2
        (datetime(2026, 3, 2, 9, 0, tzinfo=UTC), 200),    # Mar 2
        (datetime(2026, 3, 2, 16, 59, tzinfo=UTC), 400),  # Mar 2
        (datetime(2026, 3, 2, 17, 0, tzinfo=UTC), 800),   # Mar 3
    ]
    assert settlement_report(payments, date(2026, 3, 2)) == {"day": date(2026, 3, 2), "count": 3, "total_cents": 700}


def test_func_report_empty_day():
    assert settlement_report([], date(2026, 3, 2)) == {"day": date(2026, 3, 2), "count": 0, "total_cents": 0}


def test_lesson_cutoff_is_17_utc():
    assert CUTOFF_HOUR_UTC == 17
    assert cutoff_utc(date(2026, 3, 2)) == datetime(2026, 3, 2, 17, 0, tzinfo=UTC)


def test_lesson_batch_boundaries_unchanged():
    assert batch_for(datetime(2026, 3, 2, 16, 59, 59, tzinfo=UTC)) == date(2026, 3, 2)
    assert batch_for(datetime(2026, 3, 2, 17, 0, tzinfo=UTC)) == date(2026, 3, 3)
    assert batch_for(datetime(2026, 3, 2, 8, 59, tzinfo=PST)) == date(2026, 3, 2)   # 16:59 UTC
    assert batch_for(datetime(2026, 3, 2, 9, 0, tzinfo=PST)) == date(2026, 3, 3)    # 17:00 UTC
