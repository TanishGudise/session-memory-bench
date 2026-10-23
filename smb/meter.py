"""Hard spend cap. Adapted from claims-vs-reality (cvr/meter.py, same author): every call reserves its worst
case before it is made (1 token per character of input at the higher of the input and cache-write prices, plus
the full max_tokens of output, at the long-prompt price if the request could exceed 100k tokens); the
reservation is replaced by the real cost from the returned usage. A reservation that would exceed the cap is
refused and the episode stops (flagged, not scored)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

# $ per million tokens (claude-api skill model table, cached 2026-10-06). Cache writes 1.25x input (5-minute TTL),
# cache reads 0.1x input. Haiku 5.5 prompts above 100k tokens are billed at $0.50 / $2.50.
PRICES = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125, "long": 5.0},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50, "long": 1.0},
    "stub": {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0, "long": 1.0},
}
LONG_PROMPT = 100_000


class CapReached(RuntimeError):
    pass


class Meter:
    def __init__(self, cap_usd: float, ledger_path: Path | None = None, spent: float = 0.0):
        self.cap = cap_usd
        self.spent = spent
        self.reserved = 0.0
        self.lock = threading.Lock()
        self.path = ledger_path
        self._n = 0

    def worst_case(self, model, system, messages, tools, max_tokens) -> float:
        chars = len(system) + len(json.dumps(messages, default=str)) + len(json.dumps(tools))
        p = PRICES[model]
        mult = p["long"] if chars > LONG_PROMPT else 1.0
        return mult * (chars * max(p["input"], p["cache_write"]) + max_tokens * p["output"]) / 1e6

    def reserve(self, model, system, messages, tools, max_tokens) -> dict:
        w = self.worst_case(model, system, messages, tools, max_tokens)
        with self.lock:
            if self.spent + self.reserved + w > self.cap:
                raise CapReached(f"cap ${self.cap:.2f}: spent {self.spent:.4f} + reserved {self.reserved:.4f} + {w:.4f}")
            self.reserved += w
            self._n += 1
            return {"id": self._n, "amount": w}

    def release(self, ticket: dict) -> None:
        with self.lock:
            self.reserved -= ticket["amount"]

    @staticmethod
    def cost(model: str, usage: dict) -> float:
        p = PRICES[model]
        total_in = usage.get("input", 0) + usage.get("cache_read", 0) + usage.get("cache_write", 0)
        mult = p["long"] if total_in > LONG_PROMPT else 1.0
        return mult * (usage.get("input", 0) * p["input"] + usage.get("output", 0) * p["output"]
                       + usage.get("cache_read", 0) * p["cache_read"] + usage.get("cache_write", 0) * p["cache_write"]) / 1e6

    def settle(self, ticket: dict, model: str, usage: dict) -> float:
        c = self.cost(model, usage)
        with self.lock:
            self.reserved -= ticket["amount"]
            self.spent += c
            if self.path:
                with open(self.path, "a") as f:
                    f.write(json.dumps({"model": model, "usage": usage, "cost": c, "spent": self.spent}) + "\n")
                    f.flush()
        return c
