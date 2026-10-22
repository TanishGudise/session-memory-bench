from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    id: str
    email: str | None = None
    phone: str | None = None  # E.164, e.g. +14155550100
    name: str = ""
    locale: str = "en"
    tz: str = "UTC"  # IANA time zone of the user
    marketing_opt_out: bool = False
