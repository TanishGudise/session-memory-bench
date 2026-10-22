from __future__ import annotations

from notify.models import User
from notify.providers import FakeSMSProvider


def send_sms(provider: FakeSMSProvider, user: User, text: str) -> str:
    if not user.phone:
        raise ValueError(f"user {user.id} has no phone number")
    return provider.send(user.phone, text)
