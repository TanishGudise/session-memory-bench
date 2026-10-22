from __future__ import annotations

from notify.models import User
from notify.providers import FakeSMSProvider
from notify.sms import send_sms
from notify.templates import render


def send_order_shipped(provider: FakeSMSProvider, user: User, order: dict) -> str:
    text = render("order_shipped", user.locale,
                  {"order_id": order["id"], "items": ", ".join(order["items"]), "url": order["tracking_url"]})
    return send_sms(provider, user, text)


MAX_SMS_CHARS = 480  # the provider silently drops anything longer


def send_delivery_window_sms(provider: FakeSMSProvider, user: User, order: dict) -> str:
    head = f"Your order {order['id']} arrives {order['window']}: "
    tail = f". Track: {order['tracking_url']}"
    items = ", ".join(order["items"])
    room = MAX_SMS_CHARS - len(head) - len(tail)
    if len(items) > room:
        items = items[: room - 1].rstrip(", ") + "…"
    return send_sms(provider, user, head + items + tail)
