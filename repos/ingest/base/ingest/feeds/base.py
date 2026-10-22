from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ParseResult:
    records: list[dict] = field(default_factory=list)
    quarantined: list[dict] = field(default_factory=list)  # {"line": n, "raw": str, "reason": str}

    def quarantine(self, line: int, raw: object, reason: str) -> None:
        self.quarantined.append({"line": line, "raw": str(raw), "reason": reason})


Parser = Callable[[str], ParseResult]
FEEDS: dict[str, Parser] = {}


def register(name: str) -> Callable[[Parser], Parser]:
    def deco(fn: Parser) -> Parser:
        if name in FEEDS:
            raise ValueError(f"feed {name!r} registered twice")
        FEEDS[name] = fn
        return fn

    return deco
