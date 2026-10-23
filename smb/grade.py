"""Hidden-test grading.

The candidate tree is the pristine main state with only the task's editable paths taken from the agent's
workspace (files named in tasks.FORBIDDEN_NAMES are never taken). Hidden tests are added fresh, run in a
separate sandboxed process (no network, writes only in the grading dir), and the outer process decides
the score from the JUnit report: the set of test cases must equal the set of tests in the hidden files
exactly, and every `func`/`lesson` test must pass. `diag` tests are diagnostics (e.g. "followed the old
rule") and never count toward the score.
"""

from __future__ import annotations

import ast
import re
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from smb import sandbox
from smb.paths import WORK
from smb.repos import write_tree
from smb.tasks import Task

# Graded code shares a process with the hidden tests, so a determined candidate could tamper with the run. These
# references in non-test candidate files get the episode flagged; every flagged pass is hand-checked before it counts.
SUSPICIOUS = re.compile(r"junit|_pytest|\bpytest\b|atexit|os\._exit|sys\.exit|ctypes|\bgc\.|\binspect\b|sys\.modules"
                        r"|process\.exit|node:test|--test|reporter")
TS_TEST = re.compile(r"""\btest\(\s*(["'`])((?:func|lesson|diag): (?:(?!\1).)+)\1""")
TIMEOUT = 120


def candidate_tree(task: Task, workspace: dict[str, bytes]) -> dict[str, bytes]:
    tree = {rel: data for rel, data in task.base_state().items() if not task.is_editable(rel)}
    for rel, data in workspace.items():
        if task.is_editable(rel) and not rel.startswith(("tests_hidden/", "hidden/")):
            tree[rel] = data
    return tree


def expected_tests(task: Task) -> set[str]:
    names = set()
    for rel, data in task.hidden_files().items():
        if task.lang == "py" and rel.endswith(".py") and Path(rel).name.startswith("test_"):
            for node in ast.parse(data.decode()).body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    names.add(node.name)
        elif task.lang == "ts" and rel.endswith(".test.ts"):
            names.update(m.group(2) for m in TS_TEST.finditer(data.decode()))
    return names


def kind_of(name: str) -> str:
    n = name.removeprefix("test_")
    for k in ("func", "lesson", "diag"):
        if n.startswith(k):
            return k
    raise ValueError(f"hidden test without a kind prefix: {name}")


def parse_junit(path: Path) -> dict[str, str]:
    """test name -> 'pass' | 'fail' | 'skip' (duplicate names -> 'dup')."""
    out: dict[str, str] = {}
    root = ET.parse(path).getroot()
    for tc in root.iter("testcase"):
        name = tc.get("name", "")
        status = "pass"
        if tc.find("failure") is not None or tc.find("error") is not None:
            status = "fail"
        elif tc.find("skipped") is not None:
            status = "skip"
        out[name] = "dup" if name in out else status
    return out


def grade_tree(task: Task, tree: dict[str, bytes], label: str = "") -> dict:
    gdir = WORK / "grade" / f"{task.id}-{label or 'x'}-{uuid.uuid4().hex[:8]}"
    src = gdir / "src"
    try:
        write_tree(tree, src)
        hidden_root = src / ("tests_hidden" if task.lang == "py" else "hidden")
        write_tree(task.hidden_files(), hidden_root)
        junit = gdir / "junit.xml"
        env = sandbox.base_env(gdir / "home", task.grader_tz)
        if task.lang == "py":
            cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                   f"--junitxml={junit}", "tests_hidden"]
        else:
            files = sorted(p.relative_to(src).as_posix() for p in hidden_root.rglob("*.test.ts"))
            cmd = ["node", "--test", "--test-reporter=junit", f"--test-reporter-destination={junit}", *files]
        res = sandbox.run(cmd, cwd=src, write_root=gdir, env=env, timeout=TIMEOUT, pid_dir=WORK / "pids")
        expected = expected_tests(task)
        result = {"task": task.id, "label": label, "timed_out": res.timed_out, "exit": res.code,
                  "seconds": round(res.seconds, 2), "score": 0}
        tests = parse_junit(junit) if junit.exists() else {}
        if res.timed_out:
            status = "timeout"
        elif not junit.exists():
            status = "no_junit"
        elif set(tests) == expected and "dup" not in tests.values():
            status = "graded"
        elif not (set(tests) & expected) and all(v == "fail" for v in tests.values()):
            status = "collection_error"  # e.g. the module under test is missing: every hidden test fails
        else:
            status = "junit_mismatch"     # names the run should not have produced: never scored as a pass
        result["status"] = status
        if status != "graded":
            tests = {n: "fail" for n in expected}
        result["tests"] = tests
        scored = {n: v for n, v in tests.items() if kind_of(n) in ("func", "lesson")}
        result["score"] = int(status == "graded" and all(v == "pass" for v in scored.values()))
        result["func_pass"] = status == "graded" and all(v == "pass" for n, v in scored.items() if kind_of(n) == "func")
        result["lesson_pass"] = status == "graded" and all(v == "pass" for n, v in scored.items() if kind_of(n) == "lesson")
        result["diag"] = {n: v for n, v in tests.items() if kind_of(n) == "diag"}
        if result["score"] == 0:
            result["output_tail"] = res.output[-3000:]
        return result
    finally:
        shutil.rmtree(gdir, ignore_errors=True)


def suspicious(task: Task, workspace: dict[str, bytes]) -> list[str]:
    base = task.base_state()
    out = []
    for rel, data in workspace.items():
        if not task.is_editable(rel) or rel.startswith(("tests/", "test/")) or base.get(rel) == data:
            continue
        for i, line in enumerate(data.decode(errors="replace").splitlines(), 1):
            if SUSPICIOUS.search(line):
                out.append(f"{rel}:{i}: {line.strip()[:120]}")
    return out


def grade_workspace(task: Task, workspace: dict[str, bytes], label: str = "") -> dict:
    result = grade_tree(task, candidate_tree(task, workspace), label)
    result["suspicious"] = suspicious(task, workspace)
    return result


def run_visible(task_repo_tree: dict[str, bytes], lang: str, tz: str, label: str = "visible", timeout: float = 120) -> sandbox.Result:
    gdir = WORK / "visible" / f"{label}-{uuid.uuid4().hex[:8]}"
    src = gdir / "src"
    try:
        write_tree(task_repo_tree, src)
        env = sandbox.base_env(gdir / "home", tz)
        cmd = ([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] if lang == "py"
               else ["node", "--test"])
        return sandbox.run(cmd, cwd=src, write_root=gdir, env=env, timeout=timeout, pid_dir=WORK / "pids")
    finally:
        shutil.rmtree(gdir, ignore_errors=True)
