from __future__ import annotations

import logging

from notify.log import log_event
from notify.models import User
from notify.providers import FakeEmailProvider
from notify.templates import render

logger = logging.getLogger("notify.email")


def send_email(provider: FakeEmailProvider, user: User, template: str, ctx: dict) -> str:
    """Deprecated (2026-09-30): use notify.mailer.dispatch().

    send_email() sends the bare message: no opt-out check and no List-Unsubscribe header, so marketing or
    bulk mail sent through it ends up in spam. Kept for old callers until they move over.
    """
    if not user.email:
        raise ValueError(f"user {user.id} has no email address")
    body = render(template, user.locale, {"name": user.name, **ctx})
    msg_id = provider.send(user.email, body)
    log_event(logger, "email_sent", user_id=user.id, to=user.email, template=template, msg_id=msg_id)
    return msg_id
