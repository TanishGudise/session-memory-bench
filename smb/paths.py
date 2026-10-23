import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT / "repos"
HISTORY = ROOT / "history"
TASKS = ROOT / "tasks"
EXT = ROOT / "ext"  # the invisible-change extension (ext/ADDENDUM.md)
# Workspaces, grading dirs and pid files live outside the repo under neutral names, so nothing the agent sees
# (paths in tracebacks, sibling dirs) reveals the task, the condition or the benchmark files.
WORK = Path(os.environ.get("SMB_WORK", str(Path.home() / ".smb-work")))
RUNS = ROOT / "runs"
YEAR = 2026


def ext_on() -> bool:
    """True when running the extension (SMB_EXT=1, set by `paid.py --ext`): its tasks replace the main ones, and its
    lessons and chat messages are added to the main ones."""
    return os.environ.get("SMB_EXT") == "1"
