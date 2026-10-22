"""Standard retry policy (since the 2026-09-19 partner outage): 5 attempts, exponential backoff."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 5
    delays: tuple[float, ...] = (1, 2, 4, 8)  # seconds to wait before attempts 2..5


DEFAULT = RetryPolicy()


def call_with_retry(fn: Callable[[], T], retry_on: tuple[type[BaseException], ...], policy: RetryPolicy = DEFAULT,
                    sleep: Callable[[float], None] = time.sleep) -> T:
    for attempt in range(1, policy.attempts + 1):
        try:
            return fn()
        except retry_on:
            if attempt == policy.attempts:
                raise
            sleep(policy.delays[attempt - 1])
    raise AssertionError("unreachable")
