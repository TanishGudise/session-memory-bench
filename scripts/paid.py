"""Entry point for model-backed stages. Refuses to start unless the manifest equals FROZEN (or --stub).

  python scripts/paid.py history --corpus haiku-1 --repos billing --cap 0.50
  python scripts/paid.py count-raw --corpus haiku-1
  python scripts/paid.py distill --corpus haiku-1 --cap 0.25
  python scripts/paid.py eval --run pilot --corpus haiku-1 --repos billing --epochs 1 --cap 1.50
  (add --stub to any of them for a $0 run with the stub models)

Network: the API key is read from the gitignored .env and never printed. Model traffic goes through a loopback
CONNECT proxy (separate process, allowlist api.anthropic.com:443); this process installs a guard that allows
loopback connections only, so a client that ignored the proxy would fail closed. Agent code, graders and the
embedder run under sandbox-exec with no network. The proxy is stopped by its exact pid.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import manifest  # noqa: E402
from smb import netguard  # noqa: E402
from smb.agent import Limits  # noqa: E402
from smb.envfile import load_env  # noqa: E402
from smb.history import run_session  # noqa: E402
from smb.memory import corpus as corpus_mod  # noqa: E402
from smb.memory.distill import model_notes, session_text, stub_notes, write_notes  # noqa: E402
from smb.memory.provider import CONDITIONS, NoMemory, Pull, Raw, Retrieved, estimate_tokens, notes_as_chunks  # noqa: E402
from smb.memory.retriever import Index  # noqa: E402
from smb.meter import Meter  # noqa: E402
from smb.paths import RUNS, WORK  # noqa: E402
from smb.runner import done_episodes, run_episode  # noqa: E402
from smb.stub import EvalStub, HistoryStub, StubClient  # noqa: E402
from smb.tasks import all_tasks  # noqa: E402

TOTAL_CAP = 17.50
MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}


def total_spent() -> float:
    total = 0.0
    for ledger in RUNS.rglob("spend.jsonl"):
        lines = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
        total += sum(l["cost"] for l in lines)
    return total


class Session:
    """Proxy + guard + client for a paid stage (or nothing, for --stub)."""

    def __init__(self, stub: bool, log_dir: Path):
        self.stub, self.proxy = stub, None
        if stub:
            netguard.install()
            return
        if manifest.build()["manifest_sha256"] != manifest.frozen():
            raise SystemExit("manifest differs from FROZEN: refusing paid work (freeze or record an amendment first)")
        load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY missing from .env")
        log_dir.mkdir(parents=True, exist_ok=True)
        self.proxy = subprocess.Popen([sys.executable, "-m", "smb.proxy", "--allow", "api.anthropic.com:443",
                                       "--log", str(log_dir / "proxy.log")], cwd=ROOT, stdout=subprocess.PIPE, text=True,
                                      start_new_session=True)
        (WORK / "pids").mkdir(parents=True, exist_ok=True)
        (WORK / "pids" / f"proxy-{self.proxy.pid}.pid").write_text(str(self.proxy.pid))
        port = json.loads(self.proxy.stdout.readline())["port"]
        os.environ["HTTPS_PROXY"] = os.environ["https_proxy"] = f"http://127.0.0.1:{port}"
        os.environ.pop("NO_PROXY", None)
        os.environ.pop("no_proxy", None)
        netguard.install()  # loopback only: the proxy is the only way out

    def client(self, policy=None):
        if self.stub:
            return StubClient(policy)
        import anthropic
        return anthropic.Anthropic(max_retries=2)

    def close(self):
        if self.proxy is not None and self.proxy.poll() is None:
            os.kill(self.proxy.pid, signal.SIGTERM)
            self.proxy.wait(timeout=10)
            (WORK / "pids" / f"proxy-{self.proxy.pid}.pid").unlink(missing_ok=True)


def meter_for(run_dir: Path, cap: float, stub: bool) -> Meter:
    if not stub and total_spent() + cap > TOTAL_CAP:
        raise SystemExit(f"stage cap ${cap:.2f} would take the total past ${TOTAL_CAP:.2f} (spent ${total_spent():.2f})")
    run_dir.mkdir(parents=True, exist_ok=True)
    return Meter(cap_usd=cap, ledger_path=None if stub else run_dir / "spend.jsonl")


def cmd_history(a, s: Session):
    out = RUNS / "history" / a.corpus
    meter = meter_for(out, a.cap, a.stub)
    model = "stub" if a.stub else MODELS[a.model]
    specs = corpus_mod.history_specs()
    for sid, spec in sorted(specs.items(), key=lambda kv: (str(kv[1]["date"]), kv[0])):
        if spec["repo"] not in a.repos or (out / sid / "session.json").exists():
            continue
        rec = run_session(sid, s.client(HistoryStub({**spec, "id": sid})), model, out, meter=meter)
        print(json.dumps({k: rec[k] for k in ("id", "stop_task", "stop_review", "checks_failed", "calls", "cost")}), flush=True)
    print(json.dumps({"stage": "history", "spent": round(meter.spent, 4)}))


def raw_counter(s: Session, corpus: str, stub: bool):
    if stub:
        return estimate_tokens
    client, cache = s.client(), {}

    def count(text: str) -> int:
        if text not in cache:
            cache[text] = client.messages.count_tokens(model=MODELS["haiku"], messages=[{"role": "user", "content": text}]).input_tokens
        return cache[text]

    return count


def cmd_count_raw(a, s: Session):
    corpus_dir = RUNS / "history" / a.corpus
    raw = Raw(corpus_dir, raw_counter(s, a.corpus, a.stub))
    out = {repo: raw.recall("", "", {"repo": repo, "branch": ""}).meta for repo in ("billing", "notify", "inventory", "ingest")}
    (corpus_dir / "raw_blocks.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out))


def cmd_distill(a, s: Session):
    corpus_dir = RUNS / "history" / a.corpus
    meter = meter_for(corpus_dir / "distill", a.cap, a.stub)
    notes = {}
    for sid, spec in corpus_mod.history_specs().items():
        if a.stub:
            notes[sid] = stub_notes(spec)
        else:
            notes[sid], _ = model_notes(s.client(), MODELS[a.model], spec, session_text(corpus_dir, sid), meter)
    (corpus_dir / "notes_raw.json").write_text(json.dumps(notes, indent=2, ensure_ascii=False))
    write_notes(corpus_dir, notes)
    print(json.dumps({"stage": "distill", "notes": sum(len(v) for v in notes.values()), "spent": round(meter.spent, 4)}))


def cmd_eval(a, s: Session):
    corpus_dir = RUNS / "history" / a.corpus
    run_dir = RUNS / "eval" / a.run
    meter = meter_for(run_dir, a.cap, a.stub)
    model = "stub" if a.stub else MODELS[a.model]
    chunks = corpus_mod.build(corpus_dir)
    corpus_mod.save(chunks, corpus_dir / "chunks.jsonl")
    idx = Index(chunks)
    notes_idx = Index(notes_as_chunks(corpus_dir / "notes.jsonl"), embedder=idx.embedder)
    providers = {"none": NoMemory(), "raw": Raw(corpus_dir, raw_counter(s, a.corpus, a.stub)), "retrieved": Retrieved(idx),
                 "distilled": Retrieved(notes_idx, budget_chars=3500), "pull": Pull(idx)}
    conds = a.conditions or list(CONDITIONS)
    tasks = [t for t in all_tasks() if t.repo in a.repos and (not a.families or t.family in a.families)]
    done = done_episodes(run_dir)
    jobs = [(t, c, e) for e in range(1, a.epochs + 1) for t in tasks for c in conds
            if f"{t.id}__{c}__e{e}" not in done]

    def one(job):
        t, c, e = job
        client = s.client(EvalStub(t, pull=CONDITIONS[c] == "pull") if a.stub else None)
        r = run_episode(t, c, e, client, model, providers, run_dir, meter, Limits())
        print(json.dumps({k: r[k] for k in ("episode", "stop", "score", "calls", "cost")}), flush=True)
        return r

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, jobs))
    idx.close()
    print(json.dumps({"stage": "eval", "run": a.run, "episodes": len(jobs), "spent": round(meter.spent, 4)}))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("history", "count-raw", "distill", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--corpus", required=True)
        p.add_argument("--stub", action="store_true")
        p.add_argument("--model", default="haiku", choices=sorted(MODELS))
        p.add_argument("--cap", type=float, default=0.0)
        p.add_argument("--repos", nargs="*", default=["billing", "notify", "inventory", "ingest"])
        if name == "eval":
            p.add_argument("--run", required=True)
            p.add_argument("--epochs", type=int, default=1)
            p.add_argument("--conditions", nargs="*", choices=sorted(CONDITIONS))
            p.add_argument("--families", nargs="*")
            p.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    if not a.stub and a.cap <= 0 and a.cmd != "count-raw":
        raise SystemExit("--cap is required for paid stages")
    s = Session(a.stub, RUNS / "logs")
    try:
        {"history": cmd_history, "count-raw": cmd_count_raw, "distill": cmd_distill, "eval": cmd_eval}[a.cmd](a, s)
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
