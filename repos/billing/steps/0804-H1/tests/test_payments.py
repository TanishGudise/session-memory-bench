import pytest

from billing.gateway import GatewayTimeout
from billing.payments import collect_invoice


def test_collect_charges_balance(store, gateway, make_invoice):
    inv_id = make_invoice(cents=4200)
    charge_id = collect_invoice(store, gateway, inv_id)
    assert gateway.charges[charge_id]["cents"] == 4200
    assert store.fetch_invoice(inv_id).status == "paid"


def test_collect_nothing_due(store, gateway, make_invoice):
    inv_id = make_invoice(cents=4200)
    store.record_payment(inv_id, 4200, "ch_x")
    assert collect_invoice(store, gateway, inv_id) is None
    assert gateway.charges == {}


def test_timeout_after_capture_charges_once(store, gateway, make_invoice):
    inv_id = make_invoice(cents=4200)
    gateway.timeout_after_commit = 1
    charge_id = collect_invoice(store, gateway, inv_id)
    assert len(gateway.charges) == 1
    assert store.payments(inv_id) == [{"cents": 4200, "charge_id": charge_id}]


def test_gives_up_after_three_timeouts(store, gateway, make_invoice):
    inv_id = make_invoice(cents=4200)
    gateway.timeout_after_commit = 3
    with pytest.raises(GatewayTimeout):
        collect_invoice(store, gateway, inv_id)
    assert len(gateway.charges) == 1
