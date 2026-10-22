"""Partner webhooks. `http` is any object with post(url, payload) -> status code."""

from __future__ import annotations

import time
from typing import Callable

ATTEMPTS = 3
DELAY_SECONDS = 2


class WebhookFailed(Exception):
    pass


def deliver(http, url: str, payload: dict, sleep: Callable[[float], None] = time.sleep) -> int:
    """POST the payload, retrying server errors (ATTEMPTS tries, DELAY_SECONDS apart)."""
    for attempt in range(1, ATTEMPTS + 1):
        status = http.post(url, payload)
        if status < 500:
            return status
        if attempt < ATTEMPTS:
            sleep(DELAY_SECONDS)
    raise WebhookFailed(f"{url} answered {status} after {ATTEMPTS} attempts")
