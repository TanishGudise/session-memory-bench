import pytest

from notify.models import User
from notify.providers import FakeSMSProvider, ProviderUnavailable
from notify.sms import send_sms_with_retry

USER = User(id="u1", phone="+14155550100")


def test_func_first_try():
    p, sleeps = FakeSMSProvider(), []
    assert send_sms_with_retry(p, USER, "hi", sleep=sleeps.append) == "sm_0001"
    assert sleeps == []


def test_lesson_backoff_until_success():
    p, sleeps = FakeSMSProvider(), []
    p.fail_next = 4
    assert send_sms_with_retry(p, USER, "hi", sleep=sleeps.append) == "sm_0001"
    assert sleeps == [1, 2, 4, 8]


def test_lesson_gives_up_after_five_attempts():
    p, sleeps = FakeSMSProvider(), []
    p.fail_next = 5
    with pytest.raises(ProviderUnavailable):
        send_sms_with_retry(p, USER, "hi", sleep=sleeps.append)
    assert p.fail_next == 0 and p.sent == [] and sleeps == [1, 2, 4, 8]


def test_diag_old_policy_three_attempts_two_seconds():
    p, sleeps = FakeSMSProvider(), []
    p.fail_next = 2
    send_sms_with_retry(p, USER, "hi", sleep=sleeps.append)
    assert sleeps == [2, 2]
