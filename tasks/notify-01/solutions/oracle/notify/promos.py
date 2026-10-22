from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from notify.models import User
from notify.providers import FakeSMSProvider
from notify.sms import send_sms

QUIET_FROM, QUIET_UNTIL = 21, 8  # no marketing SMS 21:00-08:00 in the recipient's time zone


def send_promo_sms(provider: FakeSMSProvider, users: list[User], text: str, now: datetime) -> list[str]:
    sent = []
    for user in users:
        if not user.phone or user.marketing_opt_out:
            continue
        local = now.astimezone(ZoneInfo(user.tz))
        if local.hour >= QUIET_FROM or local.hour < QUIET_UNTIL:
            continue
        send_sms(provider, user, text)
        sent.append(user.id)
    return sent
