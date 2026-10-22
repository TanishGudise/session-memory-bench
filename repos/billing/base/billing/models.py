from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Customer:
    id: str
    email: str
    name: str = ""
    country: str = "US"


@dataclass
class Line:
    description: str
    cents: int


@dataclass
class Invoice:
    id: str
    customer_id: str
    issued: date
    due: date
    lines: list[Line] = field(default_factory=list)
    paid_cents: int = 0
    status: str = "open"  # open | paid | void
    plan: str = ""
    reminded_at: date | None = None

    @property
    def total_cents(self) -> int:
        return sum(line.cents for line in self.lines)

    @property
    def balance_cents(self) -> int:
        return self.total_cents - self.paid_cents
