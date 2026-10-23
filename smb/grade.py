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
import time
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
                        r"|__eq__|__ne__|__hash__|builtins|setattr\(|monkeypatch|\bTZ\b|tzset|os\.environ"
                        r"|process\.exit|node:test|node:assert|\bassert\b[^;\n]*\)\s*\.\w+\s*=|assert\.\w+\s*="
                        r"|defineProperty|prototype|process\.env|--test|reporter"
                        r"|assert/strict|[\"']assert[\"']|Object\.(assign|setPrototypeOf)|\btype\(\s*[\"']|__\w*\"\s*\+"
                        r"|=\s*type\b|\btype\s*,|[\"']_[\"']\s*\*|Reflect\.|\bimport\(|\bexec\(|\beval\(|__import__|getattr\("
                        r"|importlib|__class__|\bchr\(|_NodeReporter|__subclasses__|__dict__|(?<![.\w])compile\("
                        r"|sys\.argv|chmod|tests_hidden|testcase|locals\(\)|globals\(\)|process\.argv|writeFileSync|node:fs")
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


# Tests that must fail. If any passes, something in the run made failing assertions pass (a patched assertion
# function or test runner): the episode is marked tampered and scores 0. One canary per assertion helper, so
# patching any single helper is caught.
CANARY_PY = ("import pytest\n\n\ndef test_canary_eq_must_fail():\n    assert [1, 2] == [2, 1]\n\n\n"
             "def test_canary_raises_must_fail():\n    with pytest.raises(ValueError):\n        pass\n")
_TS_HELPERS = {"equal": "(1, 2)", "strictEqual": "(1, 2)", "deepEqual": "([1, 2], [2, 1])", "deepStrictEqual": "([1], [2])",
               "notEqual": "(1, 1)", "ok": "(false)", "throws": "(() => {})", "match": '("a", /b/)'}
# Node runs every test file in its own process, so the TypeScript canaries are appended to each hidden test file.
CANARY_TS = ('\nimport { test as __canaryTest } from "node:test";\nimport __canaryAssert from "node:assert/strict";\n'
             + "".join(f'__canaryTest("canary: {h}", () => {{ (__canaryAssert as any).{h}{a}; }});\n' for h, a in _TS_HELPERS.items()))
CANARY_NAMES = {"py": {"test_canary_eq_must_fail", "test_canary_raises_must_fail"},
                "ts": {f"canary: {h}" for h in _TS_HELPERS}}


def kind_of(name: str) -> str:
    n = name.removeprefix("test_")
    for k in ("func", "lesson", "diag", "canary"):
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


PYTEST_SUMMARY = re.compile(r"(\d+ (passed|failed|skipped|deselected|xfailed|xpassed|warnings?|errors?|rerun)(, )?)+"
                            r" in [\d.]+s( \(\d+:\d\d:\d\d\))?")


def _summary_agrees(lang: str, output: str, tests: dict[str, str]) -> bool:
    """The runner's own printed summary must match the JUnit counts (a report written by candidate code at import
    or at exit can't also change what the runner already printed)."""
    passed = sum(1 for v in tests.values() if v == "pass")
    failed = sum(1 for v in tests.values() if v == "fail")
    if "INTERNALERROR" in output or re.search(r"(Error|Exception|denied)[^\n]*junit|junit[^\n]*(Error|denied)", output):
        return False
    lines = [l for l in output.strip().splitlines() if l.strip()]
    if lang == "py":
        summary = [l for l in lines if PYTEST_SUMMARY.fullmatch(l.strip().strip("= ").strip())]
        # exactly one summary-shaped line, and it is the last line: a summary printed later (at exit) can't win
        if len(summary) != 1 or not lines or lines[-1] != summary[0]:
            return False
        nums = dict((k, int(v)) for v, k in re.findall(r"(\d+) (passed|failed|error|errors)", summary[0]))
        return nums.get("passed", 0) == passed and nums.get("failed", 0) == failed and not nums.get("error") and not nums.get("errors")
    # node's TAP summary is a fixed block that ends the output; earlier "# ..." lines (e.g. a child's echoed
    # console.log) don't count
    keys = ["tests", "suites", "pass", "fail", "cancelled", "skipped", "todo", "duration_ms"]
    block = lines[-len(keys):]
    if len(block) != len(keys) or any(not re.fullmatch(rf"# {k} [\d.]+", l.strip()) for k, l in zip(keys, block)):
        return False
    counts = {k: l.split()[2] for k, l in zip(keys, block)}
    return int(counts["pass"]) == passed and int(counts["fail"]) == failed


def grade_tree(task: Task, tree: dict[str, bytes], label: str = "") -> dict:
    gdir = WORK / "g" / uuid.uuid4().hex[:12]
    src = gdir / "src"
    try:
        write_tree(tree, src)
        hidden_root = src / ("tests_hidden" if task.lang == "py" else "hidden")
        write_tree(task.hidden_files(), hidden_root)
        if task.lang == "py":
            (hidden_root / "test_zz_canary.py").write_text(CANARY_PY)
        else:
            files = sorted(hidden_root.rglob("*.test.ts"))
            assert len(files) == 1, "one hidden test file per TypeScript task (one canary name)"
            files[0].write_text(files[0].read_text() + CANARY_TS)
        junit = gdir / "junit.xml"
        env = sandbox.base_env(gdir / "home", task.grader_tz)
        if task.lang == "py":
            cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                   f"--junitxml={junit}", "tests_hidden"]
        else:
            files = sorted(p.relative_to(src).as_posix() for p in hidden_root.rglob("*.test.ts"))
            cmd = ["node", "--test", "--test-reporter=junit", f"--test-reporter-destination={junit}",
                   "--test-reporter=tap", "--test-reporter-destination=stdout", *files]
        born = time.time()
        res = sandbox.run(cmd, cwd=src, write_root=gdir, env=env, timeout=TIMEOUT, pid_dir=WORK / "pids", born=born)
        if res.timed_out:  # a loaded machine can slow a correct run; retry once with twice the time
            junit.unlink(missing_ok=True)
            res = sandbox.run(cmd, cwd=src, write_root=gdir, env=env, timeout=2 * TIMEOUT, pid_dir=WORK / "pids", born=born)
        canaries = CANARY_NAMES[task.lang]
        expected = expected_tests(task) | canaries
        result = {"task": task.id, "label": label, "timed_out": res.timed_out, "exit": res.code,
                  "seconds": round(res.seconds, 2), "score": 0}
        try:
            tests = parse_junit(junit) if junit.exists() else {}
        except (ET.ParseError, OSError, ValueError, LookupError):  # a report something corrupted: never graded
            tests, junit_bad = {}, True
        else:
            junit_bad = False
        if res.timed_out:
            status = "timeout"
        elif not junit.exists() or junit_bad:
            status = "no_junit"
        elif set(tests) == expected and "dup" not in tests.values():
            if any(tests[c] != "fail" for c in canaries):
                status = "tampered"
            elif not _summary_agrees(task.lang, res.output, tests):
                status = "junit_mismatch"  # the report disagrees with what the runner printed: forged or broken
            else:
                status = "graded"
        elif not (set(tests) & (expected - canaries)) and all(v == "fail" for v in tests.values()):
            status = "collection_error"  # e.g. the module under test is missing: every hidden test fails
        else:
            status = "junit_mismatch"     # names the run should not have produced: never scored as a pass
        result["status"] = status
        if status != "graded":
            tests = {n: "fail" for n in expected - canaries}
        else:
            tests = {n: v for n, v in tests.items() if n not in canaries}
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


# Broad tripwire on top of SUSPICIOUS: candidate source (not its tests) that mentions test machinery, process
# exit hooks, directory listing or the parent directory gets a hand check, whatever it does.
TRIPWIRE = re.compile(r"(?<![.\w])test|junit|argv|summary|weakref|finalize|__del__|threading|_thread|dup2|listdir|scandir"
                      r"|\bglob\b|iterdir|\bwalk\(|readdir|[\"']\.\.[\"'/]|\.\./", re.I)


def suspicious(task: Task, workspace: dict[str, bytes]) -> list[str]:
    """Added lines (not in main's version of the file) of candidate source files that match SUSPICIOUS or TRIPWIRE."""
    base = task.base_state()
    out = []
    for rel, data in workspace.items():
        if not task.is_editable(rel) or rel.startswith(("tests/", "test/")) or base.get(rel) == data:
            continue
        old = set(base.get(rel, b"").decode(errors="replace").splitlines())
        for i, line in enumerate(data.decode(errors="replace").splitlines(), 1):
            if line not in old and (SUSPICIOUS.search(line) or TRIPWIRE.search(line)):
                out.append(f"{rel}:{i}: {line.strip()[:120]}")
    return out


def grade_workspace(task: Task, workspace: dict[str, bytes], label: str = "") -> dict:
    result = grade_tree(task, candidate_tree(task, workspace), label)
    result["suspicious"] = suspicious(task, workspace)
    return result


def run_visible(task_repo_tree: dict[str, bytes], lang: str, tz: str, label: str = "visible", timeout: float = 120) -> sandbox.Result:
    gdir = WORK / "v" / uuid.uuid4().hex[:12]
    src = gdir / "src"
    try:
        write_tree(task_repo_tree, src)
        env = sandbox.base_env(gdir / "home", tz)
        cmd = ([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] if lang == "py"
               else ["node", "--test"])
        return sandbox.run(cmd, cwd=src, write_root=gdir, env=env, timeout=timeout, pid_dir=WORK / "pids")
    finally:
        shutil.rmtree(gdir, ignore_errors=True)
