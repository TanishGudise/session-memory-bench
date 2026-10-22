from __future__ import annotations

from notify.mailer import dispatch
from notify.models import User
from notify.providers import FakeEmailProvider


def send_password_reset(provider: FakeEmailProvider, user: User, link: str) -> str | None:
    # Brand decision: German customers always get the formal (Sie) templates.
    locale = "de-formal" if user.locale == "de" else user.locale
    localized = User(**{**user.__dict__, "locale": locale})
    return dispatch(provider, localized, "password_reset", {"link": link})
