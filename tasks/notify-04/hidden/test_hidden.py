import logging

from notify.models import User
from notify.providers import FakeSMSProvider
from notify.sms import send_sms


def _send(caplog):
    caplog.set_level(logging.INFO)
    p = FakeSMSProvider()
    msg_id = send_sms(p, User(id="u-417", phone="+14155550123"), "hello")
    records = [r for r in caplog.records if r.name == "notify.sms" and "sms_sent" in r.getMessage()]
    return p, msg_id, records


def test_func_logs_sms_sent(caplog):
    p, msg_id, records = _send(caplog)
    assert p.sent[0]["body"] == "hello" and msg_id == "sm_0001"
    assert len(records) == 1
    text = records[0].getMessage()
    assert "sms_sent" in text and "u-417" in text and msg_id in text


def test_lesson_phone_number_not_logged(caplog):
    _send(caplog)
    assert "4155550123" not in caplog.text.replace(" ", "").replace("-", "")
