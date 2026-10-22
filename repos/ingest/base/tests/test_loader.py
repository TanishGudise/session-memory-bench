import pytest

from ingest.feeds import FEEDS
from ingest.loader import load
from ingest.warehouse import Warehouse
from tests.test_acme import CSV


def test_load_inserts_records():
    wh = Warehouse()
    assert load(wh, FEEDS["acme"](CSV)) == 1
    assert wh.rows[0]["external_id"] == "A-1"


def test_load_rejects_bad_records():
    from ingest.feeds.base import ParseResult
    with pytest.raises(ValueError):
        load(Warehouse(), ParseResult(records=[{"source": "x"}]))
