from __future__ import annotations

from datetime import date, datetime


def parse_us_date(text: str) -> date:
    """MM/DD/YYYY (US partners)."""
    return datetime.strptime(text.strip(), "%m/%d/%Y").date()


def parse_iso_date(text: str) -> date:
    return date.fromisoformat(text.strip())
