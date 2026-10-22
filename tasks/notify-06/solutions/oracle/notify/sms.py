from __future__ import annotations

import time
from typing import Callable

from notify.models import User
from notify.providers import FakeSMSProvider, ProviderUnavailable
from notify.retry import call_with_retry


def send_sms(provider: FakeSMSProvider, user: User, text: str) -> str:
    if not user.phone:
        raise ValueError(f"user {user.id} has no phone number")
    return provider.send(user.phone, text)


def send_sms_with_retry(provider: FakeSMSProvider, user: User, text: str,
                        sleep: Callable[[float], None] = time.sleep) -> str:
    return call_with_retry(lambda: send_sms(provider, user, text), retry_on=(ProviderUnavailable,), sleep=sleep)
