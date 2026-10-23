"""Session transcripts in the Claude Code session-JSONL shape: one record per message, `type` user/assistant,
`message` = {role, content blocks}, with uuid/parentUuid/sessionId/timestamp/cwd/gitBranch. These files are
the "prior sessions" that later conditions draw memory from."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


class TranscriptWriter:
    def __init__(self, path: Path, session_id: str, cwd: str, branch: str, start: datetime | None = None):
        self.path = path
        self.session_id = session_id
        self.cwd = cwd
        self.branch = branch
        self.parent: str | None = None
        self.clock = start  # synthetic clock for history sessions (dated in the past); real time otherwise
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")

    def _now(self) -> str:
        if self.clock is None:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.clock += timedelta(seconds=20)
        return self.clock.isoformat().replace("+00:00", "Z")

    def add(self, role: str, content: list[dict], meta: dict | None = None) -> None:
        rec = {"type": role, "uuid": str(uuid.uuid4()), "parentUuid": self.parent, "sessionId": self.session_id,
               "timestamp": self._now(), "cwd": self.cwd, "gitBranch": self.branch,
               "message": {"role": role, "content": content}}
        if meta:
            rec["meta"] = meta
        self.parent = rec["uuid"]
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
