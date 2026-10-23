from datetime import date

from billing.db import Store
from billing.gateway import FakeGateway
from billing.models import Customer, Invoice, Line
from billing.payments import collect_invoice


def test_lesson_retry_charges_once():
    s = Store()
    s.add_customer(Customer("c1", "c1@example.com"))
    s.add_invoice(Invoice("inv_1", "c1", issued=date(2026, 6, 1), due=date(2026, 6, 15), lines=[Line("Plan", 4200)]))
    gw = FakeGateway()
    gw.timeout_after_commit = 1
    collect_invoice(s, gw, "inv_1")
    assert len(gw.charges) == 1
