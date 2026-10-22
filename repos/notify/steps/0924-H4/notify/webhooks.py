"""Partner webhooks. `http` is any object with post(url, payload) -> status code."""

from __future__ import annotations

import logging
import time
from typing import Callable

from notify.log import log_event
from notify.retry import DEFAULT, call_with_retry

logger = logging.getLogger("notify.webhooks")


class WebhookFailed(Exception):
    pass


def deliver(http, url: str, payload: dict, sleep: Callable[[float], None] = time.sleep) -> int:
    """POST the payload, retrying server errors with the standard retry policy."""
    attempt = 0

    def once() -> int:
        nonlocal attempt
        attempt += 1
        status = http.post(url, payload)
        log_event(logger, "webhook_attempt", url=url, attempt=attempt, status=status, payload=payload)
        if status >= 500:
            raise WebhookFailed(f"{url} answered {status} after {attempt} attempts")
        return status

    return call_with_retry(once, retry_on=(WebhookFailed,), policy=DEFAULT, sleep=sleep)
