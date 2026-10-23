"""The agent's tools. File tools act on a per-episode workspace directory on the host, confined to it.
run_tests executes agent-written code, so it runs sandboxed (no network, writes only in the workspace)."""

from __future__ import annotations

import errno
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from smb import sandbox

MAX_RESULT = 8000
SEARCH_TIMEOUT = 10
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


MAX_FILE = 1_000_000          # bytes: bigger files are skipped by the walk and refused by read/search
MAX_SEARCH_BYTES = 20_000_000
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_WORKER_SRC = (Path(__file__).with_name("search_worker.py")).read_text()  # passed with -c: the sandbox can't read smb/


@dataclass
class Workspace:
    """Every host-side file access walks directory file descriptors from the workspace root with O_NOFOLLOW, so
    no symbolic link is ever followed, even if agent code (or a process it left running) swaps a path for a link
    between two calls."""

    root: Path
    lang: str  # "py" | "ts"
    pid_dir: Path | None = None
    test_runs: int = 0
    edits: list[str] = field(default_factory=list)

    # paths -------------------------------------------------------------------
    @staticmethod
    def _parts(rel: str | None) -> list[str]:
        rel = (rel or ".").strip()
        if rel.startswith("/") or rel.startswith("~"):
            raise ToolError("paths are relative to the repository root")
        if "\x00" in rel:
            raise ToolError("bad path")
        parts = [x for x in rel.split("/") if x not in ("", ".")]
        if ".." in parts:
            raise ToolError("'..' is not allowed in paths")
        return parts

    def _open_dir(self, parts: list[str], create: bool = False) -> int:
        """fd of the directory at parts (relative to the root), opened component by component with O_NOFOLLOW."""
        fd = os.open(self.root, _DIR_FLAGS)
        try:
            for part in parts:
                try:
                    nfd = os.open(part, _DIR_FLAGS, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    os.mkdir(part, 0o755, dir_fd=fd)
                    nfd = os.open(part, _DIR_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = nfd
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _oserror(exc: OSError, path: str) -> ToolError:
        if exc.errno in (errno.ELOOP, errno.EMLINK) or (exc.errno == errno.ENOTDIR and os.path.islink(exc.filename or "")):
            return ToolError(f"symlinks are not supported: {path}")
        if isinstance(exc, FileNotFoundError):
            return ToolError(f"no such file or directory: {path}")
        return ToolError(f"{type(exc).__name__}: {exc.strerror or exc}: {path}")

    def _read_at(self, dir_fd: int, name: str, path: str) -> bytes:
        try:
            ffd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        except OSError as exc:
            raise self._oserror(exc, path) from None
        try:
            st = os.fstat(ffd)
            if not stat.S_ISREG(st.st_mode):
                raise ToolError(f"not a regular file: {path}")
            if st.st_size > MAX_FILE:
                raise ToolError(f"file too large ({st.st_size} bytes): {path}")
            chunks, total = [], 0
            while True:
                b = os.read(ffd, 1 << 16)
                if not b:
                    return b"".join(chunks)
                total += len(b)
                if total > MAX_FILE:
                    raise ToolError(f"file too large: {path}")
                chunks.append(b)
        finally:
            os.close(ffd)

    def _read(self, path: str) -> bytes:
        parts = self._parts(path)
        if not parts or set(parts) & SKIP:
            raise ToolError(f"not a file: {path}")
        try:
            dfd = self._open_dir(parts[:-1])
        except OSError as exc:
            raise self._oserror(exc, path) from None
        try:
            return self._read_at(dfd, parts[-1], path)
        finally:
            os.close(dfd)

    def _write(self, path: str, data: bytes) -> None:
        parts = self._parts(path)
        if not parts or set(parts) & SKIP:
            raise ToolError(f"can't write: {path}")
        try:
            dfd = self._open_dir(parts[:-1], create=True)
        except OSError as exc:
            raise self._oserror(exc, path) from None
        try:
            try:
                ffd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o644, dir_fd=dfd)
            except OSError as exc:
                raise self._oserror(exc, path) from None
            try:
                if not stat.S_ISREG(os.fstat(ffd).st_mode):
                    raise ToolError(f"not a regular file: {path}")
                os.ftruncate(ffd, 0)
                view = memoryview(data)
                while view:
                    view = view[os.write(ffd, view):]
            finally:
                os.close(ffd)
        finally:
            os.close(dfd)
        self.edits.append("/".join(parts))

    def _scan(self, parts: list[str], read: bool) -> list[tuple[str, bool, bytes | None]]:
        """(relative path, is_dir, content) under parts; links never followed, unreadable or huge entries skipped."""
        out: list[tuple[str, bool, bytes | None]] = []
        if set(parts) & SKIP:
            return out
        try:
            top = self._open_dir(parts)
        except OSError:
            return out

        def walk(fd: int, prefix: list[str]) -> None:
            try:
                entries = sorted(os.scandir(fd), key=lambda e: e.name)
            except OSError:
                return
            for e in entries:
                if e.name in SKIP:
                    continue
                rel = "/".join(prefix + [e.name])
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir(follow_symlinks=False):
                        try:
                            nfd = os.open(e.name, _DIR_FLAGS, dir_fd=fd)  # fails if swapped for a link meanwhile
                        except OSError:
                            continue
                        out.append((rel, True, None))
                        try:
                            walk(nfd, prefix + [e.name])
                        finally:
                            os.close(nfd)
                    elif e.is_file(follow_symlinks=False):
                        data = None
                        if read:
                            try:
                                data = self._read_at(fd, e.name, rel)
                            except ToolError:
                                continue
                        out.append((rel, False, data))
                except OSError:
                    continue

        try:
            walk(top, list(parts))
        finally:
            os.close(top)
        return out

    def files(self) -> dict[str, bytes]:
        return {rel: data for rel, is_dir, data in self._scan([], read=True) if not is_dir and data is not None}

    # tools -------------------------------------------------------------------
    def list_dir(self, path: str = ".") -> str:
        parts = self._parts(path)
        try:
            os.close(self._open_dir(parts))
        except OSError as exc:
            raise self._oserror(exc, path) from None
        entries = [rel + ("/" if is_dir else "") for rel, is_dir, _ in self._scan(parts, read=False)]
        if len(entries) > 200:
            entries = entries[:200] + ["[more entries not shown]"]
        return "\n".join(entries) or "(empty)"

    def read_file(self, path: str) -> str:
        return _clip(self._read(path).decode("utf-8", errors="replace"))

    def search_code(self, pattern: str, path: str = ".") -> str:
        try:
            re.compile(pattern)
        except (re.error, OverflowError, RecursionError) as exc:
            raise ToolError(f"bad regular expression: {exc}")
        parts = self._parts(path)
        try:
            os.close(self._open_dir(parts))
            files = [(rel, data) for rel, is_dir, data in self._scan(parts, read=True) if not is_dir and data is not None]
        except NotADirectoryError:
            files = [("/".join(parts), self._read(path))]
        except OSError as exc:
            raise self._oserror(exc, path) from None
        payload, total = [], 0
        for rel, data in files:
            total += len(data)
            if total > MAX_SEARCH_BYTES:
                break
            payload.append([rel, data.decode("utf-8", errors="replace")])
        # the regex runs in a sandboxed child process with a deadline; it gets the contents, never paths to open
        cmd = ["/usr/bin/sandbox-exec", "-p", sandbox.profile(self.root), sys.executable, "-I", "-c", _WORKER_SRC]
        try:
            r = subprocess.run(cmd, input=json.dumps({"pattern": pattern, "files": payload}), capture_output=True,
                               text=True, timeout=SEARCH_TIMEOUT, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        except subprocess.TimeoutExpired:
            raise ToolError(f"search took longer than {SEARCH_TIMEOUT} s; use a simpler pattern")
        if r.returncode != 0:
            raise ToolError("search failed: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1][:200])
        hits = json.loads(r.stdout)
        if len(hits) > 60:
            return "\n".join(hits[:60]) + "\n[more matches not shown]"
        return "\n".join(hits) or "no matches"

    def write_file(self, path: str, content: str) -> str:
        self._write(path, content.encode("utf-8"))
        return f"wrote {len(content)} characters to {path}"

    def replace_in_file(self, path: str, old_text: str, new_text: str) -> str:
        text = self._read(path).decode("utf-8")
        n = text.count(old_text)
        if n != 1:
            raise ToolError(f"old_text occurs {n} times in {path}; it must occur exactly once")
        self._write(path, text.replace(old_text, new_text).encode("utf-8"))
        return f"replaced 1 occurrence in {path}"

    def run_tests(self, path: str | None = None) -> str:
        target = []
        if path:
            parts = self._parts(path)
            try:
                os.close(self._open_dir(parts[:-1]))
                os.lstat(os.path.join(self.root, *parts))
                if os.path.islink(os.path.join(self.root, *parts)):
                    raise ToolError(f"symlinks are not supported: {path}")
            except OSError as exc:
                raise self._oserror(exc, path) from None
            target = ["/".join(parts)]
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
        """Agent mistakes (unknown tool, bad arguments, bad paths, unreadable or oversized files) raise ToolError.
        A failure to start the sandboxed test run is the harness's and propagates."""
        fn = {"list_dir": self.list_dir, "read_file": self.read_file, "search_code": self.search_code,
              "write_file": self.write_file, "replace_in_file": self.replace_in_file, "run_tests": self.run_tests}.get(name)
        if fn is None:
            raise ToolError(f"unknown tool {name}")
        if any(not isinstance(v, str) for v in args.values()):
            raise ToolError("tool arguments must be strings")
        try:
            return fn(**args)
        except TypeError as exc:
            raise ToolError(f"bad arguments: {exc}") from None
        except (UnicodeError, ValueError, OverflowError, RecursionError, MemoryError) as exc:
            raise ToolError(f"{type(exc).__name__}: {exc}") from None
        except OSError as exc:
            if name == "run_tests":
                raise  # the sandbox failed to start: a harness error
            raise ToolError(f"{type(exc).__name__}: {exc}") from None
