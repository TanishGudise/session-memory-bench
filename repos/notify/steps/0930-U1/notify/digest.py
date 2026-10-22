from __future__ import annotations

from notify.mailer import dispatch
from notify.models import User
from notify.providers import FakeEmailProvider


def send_weekly_digest(provider: FakeEmailProvider, user: User, items: list[str]) -> str | None:
    """Weekly summary email (transactional). Nothing is sent for an empty week."""
    if not items:
        return None
    summary = "; ".join(items)
    return dispatch(provider, user, "weekly_digest", {"summary": summary})
