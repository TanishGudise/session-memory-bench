from __future__ import annotations

from notify.mailer import dispatch
from notify.models import User
from notify.providers import FakeEmailProvider


def send_newsletter(provider: FakeEmailProvider, users: list[User], body: str) -> list[str]:
    sent = []
    for user in users:
        if user.email and dispatch(provider, user, "newsletter", {"body": body}, category="marketing"):
            sent.append(user.id)
    return sent
