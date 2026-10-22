from __future__ import annotations

from decimal import Decimal

from billing.money import round_half_up


def preview_invoice(lines_cents: list[int], coupon_cents: int, tax_rate: Decimal) -> dict:
    subtotal = sum(lines_cents)
    discount = min(coupon_cents, subtotal)
    tax = round_half_up(Decimal(subtotal) * tax_rate)  # tax on the pre-discount subtotal
    return {"subtotal": subtotal, "discount": discount, "tax": tax, "total": subtotal + tax - discount}
