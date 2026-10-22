from decimal import Decimal

from billing.checkout import preview_invoice


def _norm(d):
    return {k: d[k] for k in ("subtotal", "discount", "tax", "total")}


def test_func_no_coupon():
    assert _norm(preview_invoice([1000, 999], 0, Decimal("0.08"))) == {
        "subtotal": 1999, "discount": 0, "tax": 160, "total": 2159}


def test_lesson_tax_on_discounted_subtotal():
    assert _norm(preview_invoice([10000], 2000, Decimal("0.10"))) == {
        "subtotal": 10000, "discount": 2000, "tax": 800, "total": 8800}


def test_lesson_rounding_on_discounted_subtotal():
    # (1250 - 200) * 0.07 = 73.5 -> 74 (half up)
    assert _norm(preview_invoice([1250], 200, Decimal("0.07"))) == {
        "subtotal": 1250, "discount": 200, "tax": 74, "total": 1124}


def test_diag_old_rule_tax_before_discount():
    out = preview_invoice([10000], 2000, Decimal("0.10"))
    assert out["tax"] == 1000
