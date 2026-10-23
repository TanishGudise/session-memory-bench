from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from notify.models import User
from notify.providers import FakeSMSProvider
from notify.sms import send_sms


def send_promo_sms(provider: FakeSMSProvider, users: list[User], text: str, now: datetime) -> list[str]:
    sent = []
    for user in users:
        if not user.phone or user.marketing_opt_out:
            continue
        send_sms(provider, user, text)
        sent.append(user.id)
    return sent
