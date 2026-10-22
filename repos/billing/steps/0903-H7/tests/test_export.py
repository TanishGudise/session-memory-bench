from datetime import date

from billing.reports import export_csv


def test_export_csv(store, make_invoice):
    make_invoice(cents=123456, issued=date(2026, 6, 1))
    lines = export_csv(store).splitlines()
    assert lines[0] == "id,customer,issued,total,status"
    assert lines[1] == 'inv_001,cus_1,2026-06-01,"$1,234.56",open'
