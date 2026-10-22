from datetime import date

import pytest

from billing.db import Store
from billing.gateway import FakeGateway
from billing.models import Customer, Invoice, Line
from billing.refunds import refund_invoice


def _setup(cents=90000):
    s = Store()
    s.add_customer(Customer("c1", "c1@example.com"))
    s.add_invoice(Invoice("inv_1", "c1", issued=date(2026, 6, 1), due=date(2026, 6, 15), lines=[Line("Plan", cents)]))
    s.record_payment("inv_1", cents, "ch_1")
    return s, FakeGateway()


def test_func_small_refund():
    s, gw = _setup()
    refund_id = refund_invoice(s, gw, "inv_1", 1000, requested_by="ana")
    assert gw.refunds[refund_id] == {"id": refund_id, "customer_id": "c1", "cents": 1000}
    assert s.refunds("inv_1") == [{"cents": 1000, "refund_id": refund_id}]


def test_lesson_large_refund_needs_second_approver():
    s, gw = _setup()
    with pytest.raises(Exception):
        refund_invoice(s, gw, "inv_1", 50001, requested_by="ana")
    with pytest.raises(Exception):
        refund_invoice(s, gw, "inv_1", 50001, requested_by="ana", approved_by="ana")
    assert gw.refunds == {} and s.refunds("inv_1") == []
    refund_id = refund_invoice(s, gw, "inv_1", 50001, requested_by="ana", approved_by="lee")
    assert s.refunds("inv_1") == [{"cents": 50001, "refund_id": refund_id}]


def test_lesson_exactly_500_needs_no_approver():
    s, gw = _setup()
    refund_invoice(s, gw, "inv_1", 50000, requested_by="ana")
    assert len(gw.refunds) == 1


def test_lesson_timeout_after_gateway_processed_refunds_once():
    s, gw = _setup()
    gw.timeout_after_commit = 1
    refund_id = refund_invoice(s, gw, "inv_1", 1000, requested_by="ana")
    assert list(gw.refunds) == [refund_id]
    assert s.refunds("inv_1") == [{"cents": 1000, "refund_id": refund_id}]
