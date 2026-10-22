"""Money is integer cents everywhere in billing."""

from decimal import ROUND_HALF_UP, Decimal


def to_cents(amount: str) -> int:
    """'12.34' -> 1234. Rejects more than two decimal places."""
    d = Decimal(amount)
    if d != d.quantize(Decimal("0.01")):
        raise ValueError(f"too many decimal places: {amount!r}")
    return int(d * 100)


def round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def fmt(cents: int) -> str:
    """1234 -> '$12.34', -50 -> '-$0.50'."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100:,}.{cents % 100:02d}"
