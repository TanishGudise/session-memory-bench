from datetime import date

from billing.db import Store
from billing.dunning import dunning_candidates
from billing.models import Customer, Invoice, Line

TODAY = date(2026, 7, 31)


def _store():
    s = Store()
    s.add_customer(Customer("c1", "c1@example.com"))
    return s


def _inv(s, inv_id, cents, due, paid=0, reminded=None):
    s.add_invoice(Invoice(inv_id, "c1", issued=date(2026, 6, 1), due=due, lines=[Line("Plan", cents)]))
    if paid:
        s.record_payment(inv_id, paid, f"ch_{inv_id}")
    if reminded:
        s.set_reminded(inv_id, reminded)


def test_func_overdue_rules():
    s = _store()
    _inv(s, "a", 5000, date(2026, 7, 10))                         # 21 days overdue
    _inv(s, "b", 5000, date(2026, 7, 26))                         # 5 days: too early
    _inv(s, "c", 5000, date(2026, 7, 1), reminded=date(2026, 7, 29))  # reminded 2 days ago
    _inv(s, "d", 5000, date(2026, 7, 1), reminded=date(2026, 7, 10))  # reminded 21 days ago
    _inv(s, "e", 5000, date(2026, 6, 20), paid=5000)              # paid
    _inv(s, "f", 5000, date(2026, 6, 25))                         # oldest open
    assert dunning_candidates(s, TODAY) == ["f", "d", "a"]


def test_func_partially_paid_still_reminded():
    s = _store()
    _inv(s, "a", 5000, date(2026, 7, 1), paid=3000)
    assert dunning_candidates(s, TODAY) == ["a"]


def test_lesson_no_reminders_under_five_dollars():
    s = _store()
    _inv(s, "under", 5000, date(2026, 6, 1), paid=4501)  # $4.99 left
    _inv(s, "five", 5000, date(2026, 6, 2), paid=4500)   # exactly $5.00 left
    _inv(s, "three", 300, date(2026, 6, 3))              # $3.00 invoice
    assert dunning_candidates(s, TODAY) == ["five"]


def test_diag_old_one_dollar_floor():
    s = _store()
    _inv(s, "cents", 5000, date(2026, 6, 1), paid=4901)  # 99 cents left
    _inv(s, "dollar", 5000, date(2026, 6, 2), paid=4900)  # $1.00 left
    _inv(s, "three", 300, date(2026, 6, 3))               # $3.00 invoice
    assert dunning_candidates(s, TODAY) == ["dollar", "three"]
