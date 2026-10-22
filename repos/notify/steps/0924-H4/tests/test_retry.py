import pytest

from notify.retry import RetryPolicy, call_with_retry


class Boom(Exception):
    pass


def test_policy_defaults():
    assert RetryPolicy() == RetryPolicy(5, (1, 2, 4, 8))


def test_call_with_retry():
    calls, sleeps = [], []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise Boom()
        return "ok"

    assert call_with_retry(fn, (Boom,), sleep=sleeps.append) == "ok"
    assert sleeps == [1, 2]


def test_reraises():
    with pytest.raises(Boom):
        call_with_retry(lambda: (_ for _ in ()).throw(Boom()), (Boom,), sleep=lambda s: None)
