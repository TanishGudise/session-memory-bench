"""Partner webhooks. `http` is any object with post(url, payload) -> status code."""

from __future__ import annotations

import logging
import time
from typing import Callable

from notify.log import log_event

ATTEMPTS = 3
DELAY_SECONDS = 2
logger = logging.getLogger("notify.webhooks")


class WebhookFailed(Exception):
    pass


def deliver(http, url: str, payload: dict, sleep: Callable[[float], None] = time.sleep) -> int:
    """POST the payload, retrying server errors (ATTEMPTS tries, DELAY_SECONDS apart)."""
    for attempt in range(1, ATTEMPTS + 1):
        status = http.post(url, payload)
        log_event(logger, "webhook_attempt", url=url, attempt=attempt, status=status, payload=payload)
        if status < 500:
            return status
        if attempt < ATTEMPTS:
            sleep(DELAY_SECONDS)
    raise WebhookFailed(f"{url} answered {status} after {ATTEMPTS} attempts")
