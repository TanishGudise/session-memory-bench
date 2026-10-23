import shutil
import sys
import time
import uuid

import pytest

from smb import sandbox
from smb.paths import WORK


@pytest.fixture
def tmp_path():
    """Sandboxed code can't read the system temp dirs, so these tests use a directory under SMB_WORK."""
    d = WORK / "t" / uuid.uuid4().hex[:12]
    (d / "w").mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _run(tmp_path, code, timeout=30):
    env = sandbox.base_env(tmp_path / "w" / "home", "UTC")
    return sandbox.run([sys.executable, "-c", code], cwd=tmp_path / "w", write_root=tmp_path / "w", env=env, timeout=timeout)


def test_network_is_denied(tmp_path):
    r = _run(tmp_path, "import socket\ns=socket.socket(); s.settimeout(3)\ntry:\n s.connect(('1.1.1.1', 443)); print('CONNECTED')\nexcept OSError as e: print('DENIED', e)")
    assert "DENIED" in r.output and "CONNECTED" not in r.output


def test_writes_outside_root_are_denied(tmp_path):
    outside = tmp_path / "outside.txt"
    r = _run(tmp_path, f"open({str(outside)!r}, 'w').write('x')")
    assert r.code != 0 and not outside.exists()
    inside = tmp_path / "w" / "ok.txt"
    r = _run(tmp_path, f"open({str(inside)!r}, 'w').write('x')")
    assert r.code == 0 and inside.read_text() == "x"


def test_deadline_kills_process_group(tmp_path):
    code = "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\ntime.sleep(60)"
    t0 = time.monotonic()
    r = _run(tmp_path, code, timeout=2)
    assert r.timed_out and r.code == 124 and time.monotonic() - t0 < 20


def test_benchmark_files_and_other_workspaces_are_unreadable(tmp_path):
    from smb.paths import ROOT, WORK
    other = WORK / "w" / "test-other-ws"
    other.mkdir(parents=True, exist_ok=True)
    (other / "secret.txt").write_text("x")
    own = WORK / "w" / "test-own-ws"
    own.mkdir(parents=True, exist_ok=True)
    (own / "mine.txt").write_text("ok")
    try:
        code = (
            "import sys\n"
            f"for p in [{str(ROOT / 'tasks/billing-03/hidden/test_hidden.py')!r}, {str(ROOT / 'lessons.yaml')!r}, {str(other / 'secret.txt')!r}]:\n"
            "    try:\n        open(p).read(); print('READ', p)\n    except OSError:\n        print('DENIED')\n"
            f"print(open({str(own / 'mine.txt')!r}).read())\n"
        )
        env = sandbox.base_env(own / ".home", "UTC")
        r = sandbox.run([sys.executable, "-c", code], cwd=own, write_root=own, env=env, timeout=30)
        assert r.output.count("DENIED") == 3 and "READ" not in r.output and r.output.strip().endswith("ok"), r.output
    finally:
        import shutil
        shutil.rmtree(other, ignore_errors=True)
        shutil.rmtree(own, ignore_errors=True)


def test_git_history_and_home_are_unreadable():
    import shutil
    from smb.paths import ROOT, WORK
    own = WORK / "w" / "test-git-probe"
    own.mkdir(parents=True, exist_ok=True)
    try:
        probe = ROOT / ".work" / f"home-probe-{own.name}.txt"  # a real file under $HOME, outside the workspace
        probe.parent.mkdir(exist_ok=True)
        probe.write_text("secret")
        code = (
            "import subprocess, os\n"
            f"r = subprocess.run(['git', '-C', {str(ROOT)!r}, 'show', 'HEAD:lessons.yaml'], capture_output=True, text=True)\n"
            "print('GIT', r.returncode, len(r.stdout))\n"
            f"for p in [{str(ROOT / '.git' / 'HEAD')!r}, {str(ROOT / 'smb' / 'agent.py')!r}, {str(probe)!r}]:\n"
            "    try:\n        open(p).read(); print('READ', p)\n    except PermissionError:\n        print('DENIED')\n"
            "    except OSError as e:\n        print('OTHER', type(e).__name__)\n"
        )
        env = sandbox.base_env(own / ".home", "UTC")
        r = sandbox.run([sys.executable, "-c", code], cwd=own, write_root=own, env=env, timeout=60)
        assert "READ" not in r.output and r.output.count("DENIED") == 3, r.output
        git_line = [l for l in r.output.splitlines() if l.startswith("GIT")][0]
        assert git_line.split()[1] != "0" or git_line.split()[2] == "0", r.output
    finally:
        shutil.rmtree(own, ignore_errors=True)
        (ROOT / '.work' / f'home-probe-{own.name}.txt').unlink(missing_ok=True)
