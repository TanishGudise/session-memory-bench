import pytest

from ingest.schema import validate_record

GOOD = {"source": "acme", "external_id": "A-1", "item_code": "MUG-1", "qty": 1, "amount": "1.00",
        "occurred_at": None, "exported_at": None}


def test_valid():
    validate_record(GOOD)


def test_old_sku_field_rejected():
    with pytest.raises(ValueError):
        validate_record({**GOOD, "sku": "MUG-1"})
