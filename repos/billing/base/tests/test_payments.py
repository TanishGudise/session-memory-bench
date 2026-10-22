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
