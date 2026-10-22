from datetime import date

from ingest.dates import parse_iso_date, parse_us_date


def test_dates():
    assert parse_us_date("07/04/2026") == date(2026, 7, 4)
    assert parse_iso_date("2026-07-04") == date(2026, 7, 4)
