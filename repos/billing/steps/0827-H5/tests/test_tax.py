from decimal import Decimal

from billing.tax import compute_total


def test_compute_total():
    assert compute_total([1000, 999], tax_rate=Decimal("0.08")) == {
        "subtotal": 1999, "discount": 0, "tax": 160, "total": 2159}


def test_no_tax():
    assert compute_total([500])["total"] == 500


def test_discount_after_tax():
    assert compute_total([10000], discount_cents=2000, tax_rate=Decimal("0.10")) == {
        "subtotal": 10000, "discount": 2000, "tax": 1000, "total": 9000}


def test_discount_capped_at_subtotal():
    assert compute_total([500], discount_cents=900)["discount"] == 500
