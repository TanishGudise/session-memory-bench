from datetime import date

from billing.db import Store
from billing.models import Customer, Invoice, Line
from billing.receipts import apply_payment
from billing.reports import invoice_summary


def _setup():
    s = Store()
    s.add_customer(Customer("c1", "c1@example.com"))
    s.add_invoice(Invoice("inv_1", "c1", issued=date(2026, 6, 1), due=date(2026, 6, 15), lines=[Line("Plan", 3500)]))
    return s


def test_func_single_payment():
    s = _setup()
    assert apply_payment(s, "inv_1", 1000, "ch_1") == "Invoice inv_1: paid $10.00, balance $25.00"
    assert s.get_invoice("inv_1").paid_cents == 1000


def test_lesson_second_payment_shows_current_balance():
    s = _setup()
    apply_payment(s, "inv_1", 1000, "ch_1")
    assert apply_payment(s, "inv_1", 500, "ch_2") == "Invoice inv_1: paid $5.00, balance $20.00"


def test_lesson_after_invoice_was_viewed():
    s = _setup()
    invoice_summary(s, "inv_1")  # finance looked at it earlier today
    assert apply_payment(s, "inv_1", 1000, "ch_1") == "Invoice inv_1: paid $10.00, balance $25.00"


def test_diag_stale_balance():
    s = _setup()
    apply_payment(s, "inv_1", 1000, "ch_1")
    text = apply_payment(s, "inv_1", 500, "ch_2")
    assert text.endswith("balance $30.00") or text.endswith("balance $35.00") or text.endswith("balance $25.00")
