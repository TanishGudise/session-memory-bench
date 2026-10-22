from __future__ import annotations

import time
from typing import Callable

from notify.models import User
from notify.providers import FakeSMSProvider, ProviderUnavailable


def send_sms(provider: FakeSMSProvider, user: User, text: str) -> str:
    if not user.phone:
        raise ValueError(f"user {user.id} has no phone number")
    return provider.send(user.phone, text)


def send_sms_with_retry(provider: FakeSMSProvider, user: User, text: str,
                        sleep: Callable[[float], None] = time.sleep) -> str:
    for attempt in range(1, 4):  # 3 attempts, 2 seconds apart
        try:
            return send_sms(provider, user, text)
        except ProviderUnavailable:
            if attempt == 3:
                raise
            sleep(2)
    raise AssertionError("unreachable")
