from decimal import Decimal

from billing.tax import compute_total


def test_lesson_tax_before_discount():
    out = compute_total([10000], discount_cents=2000, tax_rate=Decimal("0.10"))
    assert out["tax"] == 1000 and out["total"] == 9000
