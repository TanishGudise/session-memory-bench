from __future__ import annotations

from decimal import Decimal

from billing.money import round_half_up


def compute_total(lines_cents: list[int], tax_rate: Decimal = Decimal("0")) -> dict:
    """Subtotal, tax (rounded half up to the cent) and total, all in cents."""
    subtotal = sum(lines_cents)
    tax = round_half_up(Decimal(subtotal) * tax_rate)
    return {"subtotal": subtotal, "tax": tax, "total": subtotal + tax}
