import sys
import time

from smb import sandbox


def _run(tmp_path, code, timeout=30):
    env = sandbox.base_env(tmp_path / "home", "UTC")
    return sandbox.run([sys.executable, "-c", code], cwd=tmp_path, write_root=tmp_path / "w", env=env, timeout=timeout)


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
