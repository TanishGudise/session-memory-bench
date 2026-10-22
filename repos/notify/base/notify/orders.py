from __future__ import annotations

from notify.models import User
from notify.providers import FakeSMSProvider
from notify.sms import send_sms
from notify.templates import render


def send_order_shipped(provider: FakeSMSProvider, user: User, order: dict) -> str:
    text = render("order_shipped", user.locale,
                  {"order_id": order["id"], "items": ", ".join(order["items"]), "url": order["tracking_url"]})
    return send_sms(provider, user, text)
