from datetime import date

import pytest

from billing.db import Store
from billing.gateway import FakeGateway
from billing.models import Customer, Invoice, Line
from billing.payments import charge_late_fee


def _setup():
    s = Store()
    s.add_customer(Customer("c1", "c1@example.com"))
    s.add_invoice(Invoice("inv_1", "c1", issued=date(2026, 6, 1), due=date(2026, 6, 15), lines=[Line("Plan", 5000)]))
    return s, FakeGateway()


def test_func_late_fee():
    s, gw = _setup()
    charge_id = charge_late_fee(s, gw, "inv_1", 1500)
    assert gw.charges[charge_id] == {"id": charge_id, "customer_id": "c1", "cents": 1500}
    inv = s.get_invoice("inv_1")
    assert [(l.description, l.cents) for l in inv.lines] == [("Plan", 5000), ("Late fee", 1500)]
    assert inv.balance_cents == 5000
    assert s.payments("inv_1") == [{"cents": 1500, "charge_id": charge_id}]


def test_lesson_timeout_after_gateway_processed_charges_once():
    s, gw = _setup()
    gw.timeout_after_commit = 1
    charge_id = charge_late_fee(s, gw, "inv_1", 1500)
    assert list(gw.charges) == [charge_id]
    inv = s.get_invoice("inv_1")
    assert [(l.description, l.cents) for l in inv.lines] == [("Plan", 5000), ("Late fee", 1500)]
    assert s.payments("inv_1") == [{"cents": 1500, "charge_id": charge_id}]


def test_lesson_repeated_call_after_failure_charges_once():
    s, gw = _setup()
    gw.timeout_after_commit = 1000  # every attempt times out after the gateway processed it, however many retries
    with pytest.raises(Exception):
        charge_late_fee(s, gw, "inv_1", 1500)
    gw.timeout_after_commit = 0
    charge_id = charge_late_fee(s, gw, "inv_1", 1500)  # the job runs again
    assert list(gw.charges) == [charge_id]

