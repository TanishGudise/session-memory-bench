from datetime import date

from billing.models import Line


def test_invoice_roundtrip(store, make_invoice):
    inv_id = make_invoice(cents=2500)
    inv = store.get_invoice(inv_id)
    assert inv.total_cents == 2500
    assert inv.balance_cents == 2500
    assert inv.status == "open"


def test_payment_marks_paid(store, make_invoice):
    inv_id = make_invoice(cents=2500)
    store.record_payment(inv_id, 2500, "ch_1")
    assert store.get_invoice(inv_id).status == "paid"


def test_add_line(store, make_invoice):
    inv_id = make_invoice(cents=1000)
    store.add_line(inv_id, Line("Seat", 500))
    assert store.get_invoice(inv_id).total_cents == 1500


def test_reminded_at(store, make_invoice):
    inv_id = make_invoice()
    store.set_reminded(inv_id, date(2026, 7, 1))
    assert store.get_invoice(inv_id).reminded_at == date(2026, 7, 1)


def test_fetch_invoice_serves_report_cache(store, make_invoice):
    inv_id = make_invoice(cents=2500)
    assert store.fetch_invoice(inv_id).balance_cents == 2500
    store.record_payment(inv_id, 1000, "ch_1")
    assert store.fetch_invoice(inv_id).balance_cents == 2500  # cached until the next refresh
    assert store.get_invoice(inv_id).balance_cents == 1500
