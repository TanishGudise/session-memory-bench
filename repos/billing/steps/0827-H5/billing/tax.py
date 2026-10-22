from __future__ import annotations

from decimal import Decimal

from billing.money import round_half_up


def compute_total(lines_cents: list[int], discount_cents: int = 0, tax_rate: Decimal = Decimal("0")) -> dict:
    """Subtotal, discount, tax (rounded half up to the cent) and total, all in cents.

    Tax is computed on the subtotal before the discount; the discount comes off after tax.
    """
    subtotal = sum(lines_cents)
    discount = min(discount_cents, subtotal)
    tax = round_half_up(Decimal(subtotal) * tax_rate)
    return {"subtotal": subtotal, "discount": discount, "tax": tax, "total": subtotal + tax - discount}
