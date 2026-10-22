from datetime import date

from ingest.feeds import juniper
from ingest.schema import validate_record

CSV = "id,product,quantity,price,date\nJ-1,MUG-1,2,24.00,2026-09-30\n"


def test_func_fields():
    r = juniper.parse(CSV).records[0]
    assert (r["source"], r["external_id"], r["qty"], r["amount"], r["occurred_at"]) == (
        "juniper", "J-1", 2, "24.00", date(2026, 9, 30))


def test_lesson_records_use_current_schema():
    r = juniper.parse(CSV).records[0]
    validate_record(r)
    assert r["item_code"] == "MUG-1"


def test_diag_old_sku_field():
    assert "sku" in juniper.parse(CSV).records[0]
