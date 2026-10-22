from __future__ import annotations

import logging

from notify.log import log_event
from notify.models import User
from notify.providers import FakeEmailProvider
from notify.templates import render

logger = logging.getLogger("notify.email")


def send_email(provider: FakeEmailProvider, user: User, template: str, ctx: dict) -> str:
    """Render `template` in the user's locale and send it. Returns the provider message id."""
    if not user.email:
        raise ValueError(f"user {user.id} has no email address")
    body = render(template, user.locale, {"name": user.name, **ctx})
    msg_id = provider.send(user.email, body)
    log_event(logger, "email_sent", user_id=user.id, to=user.email, template=template, msg_id=msg_id)
    return msg_id
