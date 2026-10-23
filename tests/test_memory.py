from smb.memory.corpus import Chunk, carries
from smb.memory.provider import Oracle, hook_query
from smb.memory.retriever import Index
from smb.stats import holm, mcnemar_exact, wilson


def test_query_shape():
    q = hook_query("Add refunds.", "", {"repo": "billing", "branch": "marco/refunds"})
    assert q == "Add refunds.\nrepo: billing branch: marco/refunds"
    q2 = hook_query("Next step.", "I added refund_invoice.", {"repo": "billing", "branch": "b"})
    assert q2 == "Next step.\nI added refund_invoice.\nrepo: billing branch: b"


def test_carries_needs_a_long_enough_span():
    authored = "Support decided we don't send payment reminders for balances under $1.00 (100 cents)."
    assert carries("Review: " + authored, authored)
    assert not carries("payment reminders", authored)


def test_oracle_block():
    r = Oracle(["billing.no-dunning-under-1"]).recall("p", "", {"repo": "billing", "branch": "b"})
    assert "100 cents" in r.block and r.block.startswith("<team-memory>") and r.lessons == ["billing.no-dunning-under-1"]
    assert Oracle([]).recall("p", "", {}).block == ""


def test_bm25_only_search_is_deterministic_and_budgeted():
    chunks = [Chunk(id=f"m{i}", repo="billing", source="s", kind="review", date="2026-08-01", author="a", where="b",
                    text=f"refund rule number {i} " + "word " * 50) for i in range(20)]
    idx = Index(chunks, dense=False)
    a = idx.search("refund rule number 7", 1000)
    b = idx.search("refund rule number 7", 1000)
    assert [c.id for c in a] == [c.id for c in b] and a[0].id == "m7"
    assert sum(len(c.header()) + 1 + len(c.text) for c in a) <= 1000


def test_stats():
    lo, hi = wilson(7, 10)
    assert 0.39 < lo < 0.40 and 0.89 < hi < 0.90
    assert mcnemar_exact(0, 0) == 1.0
    assert round(mcnemar_exact(8, 1), 4) == 0.0391
    assert round(mcnemar_exact(8, 1, "greater"), 4) == 0.0195
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == {"a": 0.03, "c": 0.06, "b": 0.06}
