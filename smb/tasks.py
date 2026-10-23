from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from smb.paths import TASKS
from smb.repos import main_state, repo_language

FAMILIES = ("M", "D", "S-u", "S-s", "X", "C")
# Never taken from an agent's workspace, wherever they are (they change how tests are collected or run).
FORBIDDEN_NAMES = {"conftest.py", "sitecustomize.py", "usercustomize.py", "pytest.ini", "pyproject.toml",
                   "setup.cfg", "tox.ini", "package.json", "tsconfig.json", ".npmrc"}


@dataclass
class Task:
    id: str
    repo: str
    family: str
    lessons: list[str]
    author: str
    branch: str
    prompt: str
    editable: list[str]
    path: Path
    grader_tz: str = "America/Los_Angeles"
    extra: dict = field(default_factory=dict)

    @property
    def lang(self) -> str:
        return repo_language(self.repo)

    def hidden_files(self) -> dict[str, bytes]:
        root = self.path / "hidden"
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    def solutions(self) -> list[str]:
        d = self.path / "solutions"
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []

    def solution_state(self, name: str) -> dict[str, bytes]:
        """Main with the solution overlay applied ('noop' = main unchanged)."""
        files = dict(main_state(self.repo))
        if name == "noop":
            return files
        root = self.path / "solutions" / name
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.name != "DELETE":
                files[p.relative_to(root).as_posix()] = p.read_bytes()
        delete = root / "DELETE"
        if delete.exists():
            for line in delete.read_text().splitlines():
                files.pop(line.strip(), None)
        return files

    def base_state(self) -> dict[str, bytes]:
        """The repo state the agent starts from and the grader builds on."""
        return main_state(self.repo)

    def is_editable(self, rel: str) -> bool:
        if Path(rel).name in FORBIDDEN_NAMES or rel.endswith(".pth"):
            return False
        return any(fnmatch.fnmatchcase(rel, g) for g in self.editable)


def load(task_id: str) -> Task:
    path = TASKS / task_id
    d = yaml.safe_load((path / "task.yaml").read_text())
    known = {"id", "repo", "family", "lessons", "author", "branch", "prompt", "editable", "grader_tz"}
    t = Task(id=d["id"], repo=d["repo"], family=d["family"], lessons=list(d["lessons"]), author=d["author"],
             branch=d["branch"], prompt=d["prompt"].strip(), editable=list(d["editable"]), path=path,
             grader_tz=d.get("grader_tz", "America/Los_Angeles"), extra={k: v for k, v in d.items() if k not in known})
    assert t.id == task_id and t.family in FAMILIES, task_id
    return t


def all_tasks() -> list[Task]:
    return [load(p.name) for p in sorted(TASKS.iterdir()) if (p / "task.yaml").exists()]
