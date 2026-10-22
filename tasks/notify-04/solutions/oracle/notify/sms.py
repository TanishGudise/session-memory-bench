from __future__ import annotations

import logging

from notify.log import log_event
from notify.models import User
from notify.providers import FakeSMSProvider

logger = logging.getLogger("notify.sms")


def send_sms(provider: FakeSMSProvider, user: User, text: str) -> str:
    if not user.phone:
        raise ValueError(f"user {user.id} has no phone number")
    msg_id = provider.send(user.phone, text)
    log_event(logger, "sms_sent", user_id=user.id, to=user.phone, msg_id=msg_id)
    return msg_id
