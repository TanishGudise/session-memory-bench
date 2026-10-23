from datetime import datetime, timezone

from notify.models import User
from notify.promos import send_promo_sms
from notify.providers import FakeSMSProvider


def _u(i, n, tz, **kw):
    return User(id=i, phone=f"+1415555{n:04d}", tz=tz, **kw)


def _at(h, m=0):
    return datetime(2026, 10, 5, h, m, tzinfo=timezone.utc)


def test_func_daytime_send():
    p = FakeSMSProvider()
    users = [_u("ny", 1, "America/New_York"), _u("la", 2, "America/Los_Angeles"),
             _u("out", 3, "America/New_York", marketing_opt_out=True), User(id="nophone", tz="America/Chicago")]
    assert send_promo_sms(p, users, "20% off today", _at(18)) == ["ny", "la"]
    assert [(m["to"], m["body"]) for m in p.sent] == [("+14155550001", "20% off today"), ("+14155550002", "20% off today")]


def test_lesson_no_marketing_sms_at_night_local_time():
    p = FakeSMSProvider()
    users = [_u("ny", 1, "America/New_York"), _u("paris", 2, "Europe/Paris"), _u("tokyo", 3, "Asia/Tokyo"),
             _u("la", 4, "America/Los_Angeles"), _u("kolkata", 5, "Asia/Kolkata")]
    # 04:30 UTC: New York 00:30, Paris 06:30, Tokyo 13:30, Los Angeles 21:30 (previous day), Kolkata 10:00
    assert send_promo_sms(p, users, "hi", _at(4, 30)) == ["tokyo", "kolkata"]
    assert len(p.sent) == 2


def test_lesson_quiet_hours_boundaries():
    la = [_u("la", 1, "America/Los_Angeles")]
    assert send_promo_sms(FakeSMSProvider(), la, "hi", _at(16, 0)) == ["la"]    # 09:00 local
    assert send_promo_sms(FakeSMSProvider(), la, "hi", _at(15, 59)) == []       # 08:59 local
    sh = [_u("sh", 2, "Asia/Shanghai")]
    assert send_promo_sms(FakeSMSProvider(), sh, "hi", _at(11, 59)) == ["sh"]   # 19:59 local
    assert send_promo_sms(FakeSMSProvider(), sh, "hi", _at(12, 30)) == []       # 20:30 local
