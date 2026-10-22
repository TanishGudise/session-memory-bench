from decimal import Decimal

import pytest

from billing.money import fmt, round_half_up, to_cents


def test_to_cents():
    assert to_cents("12.34") == 1234
    assert to_cents("0.5") == 50
    with pytest.raises(ValueError):
        to_cents("1.234")


def test_fmt():
    assert fmt(1234) == "$12.34"
    assert fmt(123456789) == "$1,234,567.89"
    assert fmt(-50) == "-$0.50"


def test_round_half_up():
    assert round_half_up(Decimal("2.5")) == 3
    assert round_half_up(Decimal("2.4999")) == 2
