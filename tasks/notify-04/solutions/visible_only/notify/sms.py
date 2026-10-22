from __future__ import annotations

import logging

from notify.models import User
from notify.providers import FakeSMSProvider

logger = logging.getLogger("notify.sms")


def send_sms(provider: FakeSMSProvider, user: User, text: str) -> str:
    if not user.phone:
        raise ValueError(f"user {user.id} has no phone number")
    msg_id = provider.send(user.phone, text)
    logger.info("sms_sent user_id=%s to=%s msg_id=%s", user.id, user.phone, msg_id)
    return msg_id
