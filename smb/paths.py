import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT / "repos"
HISTORY = ROOT / "history"
TASKS = ROOT / "tasks"
# Workspaces, grading dirs and pid files live outside the repo under neutral names, so nothing the agent sees
# (paths in tracebacks, sibling dirs) reveals the task, the condition or the benchmark files.
WORK = Path(os.environ.get("SMB_WORK", str(Path.home() / ".smb-work")))
RUNS = ROOT / "runs"
YEAR = 2026
