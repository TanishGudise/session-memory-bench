"""Run untrusted code (agent-written or graded) under macOS sandbox-exec: no network except loopback/unix
sockets, file writes only inside one directory. Every run has a deadline; on timeout the whole process
group is killed by its exact pgid (the child is started in its own session)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path


def profile(write_root: Path, extra_reads: tuple[Path, ...] = ()) -> str:
    """No network; writes only inside write_root; no file data reads anywhere under the home directory (the
    benchmark repo with its .git, other workspaces, other projects) or in the shared temp dirs, except write_root,
    the project's venv and `extra_reads`."""
    from smb.paths import ROOT
    w = str(write_root.resolve())
    deny = " ".join(f'(subpath "{d}")' for d in (str(Path.home().resolve()), "/private/tmp", "/private/var/folders"))
    allow = " ".join(f'(subpath "{d}")' for d in (w, str((ROOT / ".venv").resolve()), *(str(Path(x).resolve()) for x in extra_reads)))
    return (
        "(version 1)\n(allow default)\n"
        "(deny network-outbound)\n(deny network-inbound)\n(deny network-bind)\n"
        '(allow network-outbound (remote unix-socket))\n'
        f"(deny file-read-data {deny})\n"
        f"(allow file-read-data {allow})\n"
        '(deny file-write*)\n'
        f'(allow file-write* (subpath "{w}") (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr")'
        ' (literal "/dev/tty") (regex #"^/dev/fd/"))\n'
    )


@dataclass
class Result:
    code: int
    output: str
    timed_out: bool
    seconds: float


def run(cmd: list[str], cwd: Path, write_root: Path, env: dict[str, str], timeout: float,
        pid_dir: Path | None = None, max_output: int = 200_000) -> Result:
    """Run `cmd` sandboxed. Output goes to a file inside write_root (no pipes a daemon could hold)."""
    write_root.mkdir(parents=True, exist_ok=True)
    out_path = write_root / f".out-{os.getpid()}-{time.monotonic_ns()}"
    full = ["/usr/bin/sandbox-exec", "-p", profile(write_root), *cmd]
    t0 = time.monotonic()
    with open(out_path, "wb") as out:
        proc = subprocess.Popen(full, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                start_new_session=True)
    pid_file = None
    if pid_dir is not None:
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_file = pid_dir / f"{proc.pid}.pid"
        pid_file.write_text(f"{proc.pid}\n{' '.join(cmd[:3])}\n")
    timed_out = threading.Event()

    def kill():
        timed_out.set()
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # pgid == pid (new session)
        except ProcessLookupError:
            pass

    timer = threading.Timer(timeout, kill)
    timer.start()
    try:
        code = proc.wait()
    finally:
        timer.cancel()
        try:  # leftovers of the group (background children) die with the run
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if pid_file is not None:
            pid_file.unlink(missing_ok=True)
    data = out_path.read_bytes()
    out_path.unlink(missing_ok=True)
    text = data[:max_output].decode("utf-8", errors="replace")
    if len(data) > max_output:
        text += f"\n[output truncated: {len(data)} bytes]"
    return Result(code=124 if timed_out.is_set() else code, output=text, timed_out=timed_out.is_set(),
                  seconds=time.monotonic() - t0)


def base_env(home: Path, tz: str) -> dict[str, str]:
    tmp = home / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": f"{Path(sys.executable).parent}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
        "HOME": str(home), "TMPDIR": str(tmp), "TZ": tz, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUNBUFFERED": "1",
        "NODE_NO_WARNINGS": "1", "NO_COLOR": "1",
    }
