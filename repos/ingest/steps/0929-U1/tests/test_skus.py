from ingest.feeds import FEEDS
from ingest.skus import normalize_sku


def test_normalize():
    assert normalize_sku(" ab-12 ") == "AB-12"


def test_acme_normalizes():
    result = FEEDS["acme"]("order_id,sku,qty,amount,ordered_at,exported_at\nA-1, mug-1 ,1,1.00,07/04/2026,\n")
    assert result.records[0]["item_code"] == "MUG-1"
