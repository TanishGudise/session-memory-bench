from datetime import date

import pytest

from billing.db import Store
from billing.gateway import FakeGateway
from billing.models import Customer, Invoice, Line


@pytest.fixture
def store():
    s = Store()
    s.add_customer(Customer(id="cus_1", billing_email="ana@example.com", name="Ana"))
    return s


@pytest.fixture
def gateway():
    return FakeGateway()


@pytest.fixture
def make_invoice(store):
    counter = {"n": 0}

    def make(cents=1000, customer_id="cus_1", issued=date(2026, 6, 1), due=date(2026, 6, 15), **kw):
        counter["n"] += 1
        inv = Invoice(id=f"inv_{counter['n']:03d}", customer_id=customer_id, issued=issued, due=due,
                      lines=[Line("Pro plan", cents)], **kw)
        store.add_invoice(inv)
        return inv.id

    return make
