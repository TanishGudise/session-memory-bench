"""Partner webhooks. `http` is any object with post(url, payload) -> status code."""

from __future__ import annotations


class WebhookFailed(Exception):
    pass


def deliver(http, url: str, payload: dict) -> int:
    status = http.post(url, payload)
    if status >= 500:
        raise WebhookFailed(f"{url} answered {status}")
    return status
