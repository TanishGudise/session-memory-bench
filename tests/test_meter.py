import pytest

from smb.meter import CapReached, Meter


def test_reserve_settle_and_cap():
    m = Meter(cap_usd=0.02)
    t = m.reserve("claude-haiku-5-5", "s" * 1000, [{"role": "user", "content": "x" * 10_000}], [], 8000)
    assert 0.001 < t["amount"] < 0.01
    cost = m.settle(t, "claude-haiku-5-5", {"input": 1000, "output": 500, "cache_read": 10_000, "cache_write": 2000})
    assert cost == pytest.approx((1000 * 0.10 + 500 * 0.50 + 10_000 * 0.01 + 2000 * 0.125) / 1e6)
    with pytest.raises(CapReached):
        m.reserve("claude-haiku-5-5", "", [{"role": "user", "content": "x" * 200_000}], [], 8000)


def test_long_prompt_tier():
    base = Meter.cost("claude-haiku-5-5", {"input": 90_000, "output": 1000})
    long = Meter.cost("claude-haiku-5-5", {"input": 110_000, "output": 1000})
    assert long == pytest.approx(5 * (110_000 * 0.10 + 1000 * 0.50) / 1e6) and base < long
