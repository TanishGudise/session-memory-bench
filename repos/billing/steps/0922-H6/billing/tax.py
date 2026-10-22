from __future__ import annotations

from decimal import Decimal

from billing.money import round_half_up


def compute_total(lines_cents: list[int], discount_cents: int = 0, tax_rate: Decimal = Decimal("0")) -> dict:
    """Subtotal, discount, tax (rounded half up to the cent) and total, all in cents.

    Tax is computed on the discounted subtotal (finance rule since 2026-10-01).
    """
    subtotal = sum(lines_cents)
    discount = min(discount_cents, subtotal)
    taxable = subtotal - discount
    tax = round_half_up(Decimal(taxable) * tax_rate)
    return {"subtotal": subtotal, "discount": discount, "tax": tax, "total": taxable + tax}
