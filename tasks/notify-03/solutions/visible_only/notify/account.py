from __future__ import annotations

from notify.mailer import dispatch
from notify.models import User
from notify.providers import FakeEmailProvider


def send_password_reset(provider: FakeEmailProvider, user: User, link: str) -> str | None:
    return dispatch(provider, user, "password_reset", {"link": link})
