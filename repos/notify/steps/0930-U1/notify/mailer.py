"""Email dispatch (replaces email.send_email, 2026-09-30)."""

from __future__ import annotations

import logging

from notify.log import log_event
from notify.models import User
from notify.providers import FakeEmailProvider
from notify.templates import render

logger = logging.getLogger("notify.mailer")
UNSUBSCRIBE_URL = "https://larkspur.example/u/{user_id}/{category}"


def dispatch(provider: FakeEmailProvider, user: User, template: str, ctx: dict,
             category: str = "transactional") -> str | None:
    """Render and send an email. Returns the provider message id, or None if the user opted out.

    Marketing email is skipped for users who opted out, and carries the List-Unsubscribe headers that the
    big mailbox providers require for bulk mail (without them it goes to spam).
    """
    if not user.email:
        raise ValueError(f"user {user.id} has no email address")
    if category == "marketing" and user.marketing_opt_out:
        log_event(logger, "email_skipped_opt_out", user_id=user.id, template=template)
        return None
    body = render(template, user.locale, {"name": user.name, **ctx})
    headers = {}
    if category == "marketing":
        headers["List-Unsubscribe"] = "<" + UNSUBSCRIBE_URL.format(user_id=user.id, category=category) + ">"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg_id = provider.send(user.email, body, headers=headers)
    log_event(logger, "email_sent", user_id=user.id, to=user.email, template=template, category=category, msg_id=msg_id)
    return msg_id
