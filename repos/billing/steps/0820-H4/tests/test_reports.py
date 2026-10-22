from datetime import date

from billing.reports import overdue_invoices


def test_overdue_oldest_first(store, make_invoice):
    a = make_invoice(cents=1000, due=date(2026, 6, 20))
    b = make_invoice(cents=2000, due=date(2026, 6, 10))
    make_invoice(cents=3000, due=date(2026, 7, 30))  # not yet due
    rows = overdue_invoices(store, date(2026, 7, 1))
    assert [r["id"] for r in rows] == [b, a]
    assert rows[0]["days_overdue"] == 21


def test_paid_invoices_are_not_overdue(store, make_invoice):
    a = make_invoice(cents=1000, due=date(2026, 6, 20))
    store.record_payment(a, 1000, "ch_1")
    assert overdue_invoices(store, date(2026, 7, 1)) == []
