from __future__ import annotations

from decimal import Decimal

from billing.tax import compute_total


def preview_invoice(lines_cents: list[int], coupon_cents: int, tax_rate: Decimal) -> dict:
    return compute_total(lines_cents, discount_cents=coupon_cents, tax_rate=tax_rate)
