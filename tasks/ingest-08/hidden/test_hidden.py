from datetime import date

from ingest.feeds import contoso

CSV = "invoice_no,sku,qty,amount,invoice_date\nC-1,MUG-1,2,1234.50,2026-09-30\nC-2,CUP-2,1,0.10,2026-09-30\n"


def _code(r):
    return r.get("item_code", r.get("sku"))


def test_func_fields():
    recs = contoso.parse(CSV).records
    assert [(r["source"], r["external_id"], _code(r), r["qty"], r["occurred_at"]) for r in recs] == [
        ("contoso", "C-1", "MUG-1", 2, date(2026, 9, 30)), ("contoso", "C-2", "CUP-2", 1, date(2026, 9, 30))]


def test_lesson_amounts_kept_as_received_strings():
    assert [r["amount"] for r in contoso.parse(CSV).records] == ["1234.50", "0.10"]


def test_diag_amounts_converted_to_cents():
    assert [r["amount"] for r in contoso.parse(CSV).records] == [123450, 10]
