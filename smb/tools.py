"""The agent's tools. File tools act on a per-episode workspace directory on the host, confined to it.
run_tests executes agent-written code, so it runs sandboxed (no network, writes only in the workspace)."""

from __future__ import annotations

import os
import re
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

from smb import sandbox

MAX_RESULT = 8000
DEV_TZ = "America/Los_Angeles"  # the developer laptop the agent "runs" on; CI and graders differ
SKIP = {"__pycache__", ".pytest_cache", "node_modules", ".tmp", ".home"}

TOOL_SPECS = [
    {"name": "list_dir", "description": "List the files and directories under a path in the repository (recursively, up to 200 entries).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory relative to the repository root. Default '.'."}},
                      "additionalProperties": False}},
    {"name": "read_file", "description": "Read a text file from the repository.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}},
    {"name": "search_code", "description": "Search the repository's files for a regular expression. Returns matching lines as path:line: text.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "description": "Directory to search. Default '.'."}},
                      "required": ["pattern"], "additionalProperties": False}},
    {"name": "write_file", "description": "Create or overwrite a file with the given content.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"], "additionalProperties": False}},
    {"name": "replace_in_file", "description": "Replace exactly one occurrence of old_text with new_text in a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
                      "required": ["path", "old_text", "new_text"], "additionalProperties": False}},
    {"name": "run_tests", "description": "Run the repository's test suite (or one test file or directory) and return the output.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Optional test file or directory."}},
                      "additionalProperties": False}},
    {"name": "finish", "description": "Call this when you are done, with a short summary of what you changed.",
     "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": False}},
]
SEARCH_MEMORY_SPEC = {
    "name": "search_memory",
    "description": "Search your team's memory: earlier agent sessions, PR reviews and team chat. Returns the most relevant dated entries.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
}


class ToolError(Exception):
    pass


def _clip(text: str, limit: int = MAX_RESULT) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n[truncated: {len(text)} characters in total]"


@dataclass
class Workspace:
    root: Path
    lang: str  # "py" | "ts"
    pid_dir: Path | None = None
    test_runs: int = 0
    edits: list[str] = field(default_factory=list)

    def _resolve(self, rel: str | None, must_exist: bool = True) -> Path:
        rel = (rel or ".").strip()
        if rel.startswith("/") or rel.startswith("~"):
            raise ToolError("paths are relative to the repository root")
        p = (self.root / rel).resolve()
        root = self.root.resolve()
        if p != root and root not in p.parents:
            raise ToolError("path is outside the repository")
        cur = root
        for part in p.relative_to(root).parts:
            cur = cur / part
            if cur.is_symlink():
                raise ToolError("symlinks are not supported")
        if must_exist and not p.exists():
            raise ToolError(f"no such file or directory: {rel}")
        return p

    def _walk(self, base: Path):
        """Regular files under base, never following or listing symlinks (agent code can create them)."""
        root = self.root.resolve()
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(self.root)
            if set(rel.parts) & SKIP or any((self.root / Path(*rel.parts[: i + 1])).is_symlink() for i in range(len(rel.parts))):
                continue
            if root != p.resolve() and root not in p.resolve().parents:
                continue
            yield p, rel

    def files(self) -> dict[str, bytes]:
        out = {}
        for p, rel in self._walk(self.root):
            if p.is_file() and stat.S_ISREG(p.lstat().st_mode):
                try:
                    out[rel.as_posix()] = p.read_bytes()
                except OSError:  # e.g. a file the agent's own code made unreadable
                    continue
        return out

    # tools -----------------------------------------------------------------
    def list_dir(self, path: str = ".") -> str:
        base = self._resolve(path)
        if not base.is_dir():
            raise ToolError(f"not a directory: {path}")
        entries = []
        for p, rel in self._walk(base):
            entries.append(rel.as_posix() + ("/" if p.is_dir() else ""))
            if len(entries) >= 200:
                entries.append("[more entries not shown]")
                break
        return "\n".join(entries) or "(empty)"

    def _regular(self, p: Path, path: str) -> None:
        if p.exists() and not stat.S_ISREG(p.lstat().st_mode):
            raise ToolError(f"not a regular file: {path}")

    def read_file(self, path: str) -> str:
        p = self._resolve(path)
        if not p.is_file():
            raise ToolError(f"not a file: {path}")
        self._regular(p, path)
        return _clip(p.read_text(encoding="utf-8", errors="replace"))

    def search_code(self, pattern: str, path: str = ".") -> str:
        try:
            rx = re.compile(pattern)
        except (re.error, OverflowError, RecursionError) as exc:
            raise ToolError(f"bad regular expression: {exc}")
        base = self._resolve(path)
        hits = []
        candidates = list(self._walk(base)) if base.is_dir() else [(base, base.relative_to(self.root))]
        for p, rel in candidates:
            if not p.is_file() or not stat.S_ISREG(p.lstat().st_mode) or set(rel.parts) & SKIP:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel.as_posix()}:{i}: {line.strip()[:200]}")
                    if len(hits) >= 60:
                        return "\n".join(hits) + "\n[more matches not shown]"
        return "\n".join(hits) or "no matches"

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path, must_exist=False)
        self._regular(p, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        self.edits.append(p.relative_to(self.root).as_posix())
        return f"wrote {len(content)} characters to {path}"

    def replace_in_file(self, path: str, old_text: str, new_text: str) -> str:
        p = self._resolve(path)
        self._regular(p, path)
        text = p.read_text(encoding="utf-8")
        n = text.count(old_text)
        if n != 1:
            raise ToolError(f"old_text occurs {n} times in {path}; it must occur exactly once")
        p.write_text(text.replace(old_text, new_text), encoding="utf-8")
        self.edits.append(p.relative_to(self.root).as_posix())
        return f"replaced 1 occurrence in {path}"

    def run_tests(self, path: str | None = None) -> str:
        target = [] if not path else [self._resolve(path).relative_to(self.root).as_posix()]
        self.test_runs += 1
        env = sandbox.base_env(self.root / ".home", DEV_TZ)
        if self.lang == "py":
            cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *target]
        else:
            cmd = ["node", "--test", *target]
        res = sandbox.run(cmd, cwd=self.root, write_root=self.root, env=env, timeout=120, pid_dir=self.pid_dir)
        tail = res.output[-6000:] if len(res.output) > 6000 else res.output
        note = "[timed out after 120 s]\n" if res.timed_out else ""
        return f"{note}exit code {res.code}\n{tail}"

    def call(self, name: str, args: dict) -> str:
        """Agent mistakes (unknown tool, bad arguments, bad paths, unreadable files) raise ToolError. A failure to
        start the sandboxed test run is the harness's and propagates."""
        fn = {"list_dir": self.list_dir, "read_file": self.read_file, "search_code": self.search_code,
              "write_file": self.write_file, "replace_in_file": self.replace_in_file, "run_tests": self.run_tests}.get(name)
        if fn is None:
            raise ToolError(f"unknown tool {name}")
        if any(not isinstance(v, str) for v in args.values()):
            raise ToolError("tool arguments must be strings")
        if name == "run_tests":
            target = args.get("path")
            if target is not None:
                try:
                    self._resolve(target)
                except (OSError, ValueError) as exc:
                    raise ToolError(f"bad path: {type(exc).__name__}: {exc}") from None
            try:
                return fn(**args)
            except TypeError as exc:
                raise ToolError(f"bad arguments: {exc}") from None
        try:
            return fn(**args)
        except TypeError as exc:
            raise ToolError(f"bad arguments: {exc}") from None
        except (OSError, UnicodeError, ValueError, OverflowError, RecursionError, re.error) as exc:
            raise ToolError(f"{type(exc).__name__}: {exc}") from None
