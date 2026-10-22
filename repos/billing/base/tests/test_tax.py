from decimal import Decimal

from billing.tax import compute_total


def test_compute_total():
    assert compute_total([1000, 999], Decimal("0.08")) == {"subtotal": 1999, "tax": 160, "total": 2159}


def test_no_tax():
    assert compute_total([500])["total"] == 500
