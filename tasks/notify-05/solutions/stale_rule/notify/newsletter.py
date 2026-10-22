from __future__ import annotations

from notify.email import send_email
from notify.models import User
from notify.providers import FakeEmailProvider


def send_newsletter(provider: FakeEmailProvider, users: list[User], body: str) -> list[str]:
    sent = []
    for user in users:
        if user.email:
            send_email(provider, user, "newsletter", {"body": body})
            sent.append(user.id)
    return sent
