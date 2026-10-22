from datetime import date

from billing.db import Store
from billing.models import Customer, Invoice, Line
from billing.reports import statement_text


def test_func_statement():
    s = Store()
    s.add_customer(Customer("c1", "c1@example.com"))
    s.add_customer(Customer("c2", "c2@example.com"))
    s.add_invoice(Invoice("inv_b", "c1", issued=date(2026, 7, 1), due=date(2026, 7, 15), lines=[Line("Plan", 123456)]))
    s.add_invoice(Invoice("inv_a", "c1", issued=date(2026, 6, 1), due=date(2026, 6, 15), lines=[Line("Plan", 5000)]))
    s.add_invoice(Invoice("inv_c", "c2", issued=date(2026, 6, 5), due=date(2026, 6, 20), lines=[Line("Plan", 700)]))
    s.record_payment("inv_a", 5000, "ch_1")
    s.record_payment("inv_b", 6, "ch_2")
    lines = statement_text(s, "c1").strip().splitlines()
    assert [l.split() for l in lines] == [
        ["inv_a", "2026-06-01", "$50.00", "paid"],
        ["inv_b", "2026-07-01", "$1,234.56", "open"],
        ["Balance:", "$1,234.50"],
    ]


def test_func_no_invoices():
    s = Store()
    s.add_customer(Customer("c1", "c1@example.com"))
    assert statement_text(s, "c1").strip().splitlines() == ["Balance: $0.00"]
