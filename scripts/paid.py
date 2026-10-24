"""Entry point for model-backed stages. Refuses to start unless the manifest equals FROZEN (or --stub).

  pilot:  history --stage pilot --corpus c1 --repos billing; distill --stage pilot --corpus c1 --repos billing;
          label_notes.py c1 (review by hand); freeze-corpus --corpus c1 --repos billing;
          eval --stage pilot --run pilot --corpus c1 --repos billing;
          eval --stage pilot --run pilot --corpus c1 --repos notify inventory ingest --families M --conditions a g
  then:   history --stage history --corpus c1 --repos notify inventory ingest; distill (same); label_notes.py c1;
          freeze-corpus --corpus c1 (all repos; extends the pilot freeze); eval --stage main --run main --corpus c1 --epochs 5 (Amendment 1);
          eval --stage sonnet --model sonnet --run sonnet --corpus c1 --families S-u S-s --conditions a c
  (add --stub to any of them for a $0 run with the stub models)

Spend: each stage has the cap registered in PREREGISTRATION.md (STAGE_CAPS); its meter starts from what that stage
already spent according to every spend.jsonl under runs/, and the total across stages is capped too. The SDK
client makes no retries of its own: the agent loop retries, reserving again for every attempt.

Network: the API key is read from the gitignored .env and never printed. Model traffic goes through a loopback
CONNECT proxy (separate process, allowlist api.anthropic.com:443); this process installs a guard that allows
loopback connections only, so a client that ignored the proxy would fail closed. Agent code, graders and the
embedder run under sandbox-exec with no network. The proxy is stopped by its exact pid.
"""

from __future__ import annotations

import argparse
import fcntl
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
from smb.memory.freeze import freeze, load_frozen, stub_labels  # noqa: E402
from smb.memory.provider import CONDITIONS, FrozenRaw, NoMemory, Pull, Retrieved, distilled_index_chunks_from, estimate_tokens  # noqa: E402
from smb.memory.retriever import Index  # noqa: E402
from smb.meter import Meter  # noqa: E402
from smb.paths import RUNS, WORK  # noqa: E402
from smb.runner import done_episodes, run_episode  # noqa: E402
from smb.stub import EvalStub, HistoryStub, StubClient  # noqa: E402
from smb.tasks import all_tasks  # noqa: E402

TOTAL_CAP = 17.50
STAGE_CAPS = {"pilot": 1.50, "history": 1.00, "main": 12.00, "sonnet": 3.00, "ext": 3.00}  # ext: ext/ADDENDUM.md
MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}


def spent(stage: str | None = None) -> float:
    """Dollars already booked (all stages, or one), from every spend ledger under runs/."""
    total = 0.0
    for ledger in RUNS.rglob("spend.jsonl"):
        for line in ledger.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if stage is None or rec.get("stage") == stage:
                    total += rec["cost"]
    return total


def on_ac_power() -> bool | None:
    """True on AC power, False on battery, None when pmset can't tell."""
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return "AC Power" in out


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
        return anthropic.Anthropic(max_retries=0)  # retries happen in the agent loop, each with a fresh reservation

    def close(self):
        if self.proxy is not None and self.proxy.poll() is None:
            os.kill(self.proxy.pid, signal.SIGTERM)
            self.proxy.wait(timeout=10)
            (WORK / "pids" / f"proxy-{self.proxy.pid}.pid").unlink(missing_ok=True)


def meter_for(run_dir: Path, stage: str, stub: bool) -> Meter:
    run_dir.mkdir(parents=True, exist_ok=True)
    if stub:
        return Meter(cap_usd=0.0)
    cap = STAGE_CAPS[stage]
    other = spent() - spent(stage)
    if other + cap > TOTAL_CAP:
        raise SystemExit(f"stage {stage} (${cap:.2f}) would take the total past ${TOTAL_CAP:.2f} (other stages ${other:.2f})")
    return Meter(cap_usd=cap, ledger_path=run_dir / "spend.jsonl", spent=spent(stage), stage=stage)


def cmd_history(a, s: Session):
    out = RUNS / "history" / a.corpus
    meter = meter_for(out, a.stage, a.stub)
    model = "stub" if a.stub else MODELS[a.model]
    specs = corpus_mod.history_specs()
    for sid, spec in sorted(specs.items(), key=lambda kv: (str(kv[1]["date"]), kv[0])):
        if spec["repo"] not in a.repos or (out / sid / "session.json").exists():
            continue
        rec = run_session(sid, s.client(HistoryStub({**spec, "id": sid})), model, out, meter=meter)
        print(json.dumps({k: rec[k] for k in ("id", "stop_task", "stop_review", "complete", "checks_failed", "calls", "cost")}), flush=True)
        if not rec["complete"]:
            reason = rec.get("problem") or "incomplete session (spend cap)"
            print(json.dumps({"stopped": sid, "reason": f"{reason}; resume runs it again"}))
            break
    print(json.dumps({"stage": "history", "spent": round(meter.spent, 4)}))


def token_counter(s: Session, stub: bool):
    if stub:
        return estimate_tokens
    client, cache = s.client(), {}

    def count(text: str) -> int:  # the Messages API token counter (free), for the main run's model
        if text not in cache:
            cache[text] = client.messages.count_tokens(model=MODELS["haiku"], messages=[{"role": "user", "content": text}]).input_tokens
        return cache[text]

    return count


def cmd_freeze_corpus(a, s: Session):
    corpus_dir = RUNS / "history" / a.corpus
    if a.stub and not (corpus_dir / "notes_labels.json").exists():
        stub_labels(corpus_dir)
    allowed = set(json.loads(Path(a.allow_leaks).read_text())) if a.allow_leaks else None
    m = freeze(corpus_dir, token_counter(s, a.stub), allowed, repos=a.repos, force=a.force)
    print(json.dumps({"corpus_sha256": m["sha256"], "repos": m["repos"], "chunks": m["chunks"], "notes": m["notes"], "raw": m["raw"]}))


def cmd_distill(a, s: Session):
    corpus_dir = RUNS / "history" / a.corpus
    meter = meter_for(corpus_dir / "distill", a.stage, a.stub)
    raw_path = corpus_dir / "notes_raw.json"
    notes = json.loads(raw_path.read_text()) if raw_path.exists() else {}  # earlier repos' notes are kept
    for sid, spec in corpus_mod.history_specs().items():
        if spec["repo"] not in a.repos or sid in notes:
            continue
        if a.stub:
            notes[sid] = stub_notes(spec)
        else:
            notes[sid], _ = model_notes(s.client(), MODELS[a.model], spec, session_text(corpus_dir, sid), meter)
        raw_path.write_text(json.dumps(notes, indent=2, ensure_ascii=False))  # after every session: nothing paid is lost
    write_notes(corpus_dir, notes)
    print(json.dumps({"stage": "distill", "notes": sum(len(v) for v in notes.values()), "spent": round(meter.spent, 4)}))


def cmd_eval(a, s: Session):
    corpus_dir = RUNS / "history" / a.corpus
    run_dir = RUNS / "eval" / a.run
    cm, blobs = load_frozen(corpus_dir)
    if a.stage == "ext":  # an extension run on a corpus without the extension's chat would be invalid (checked before any run file)
        import yaml
        have = {c.source for c in corpus_mod.loads(blobs["chunks.jsonl"].decode())}
        want = {m["id"] for m in yaml.safe_load((ROOT / "ext" / "chat.yaml").read_text())["messages"]}
        if not want <= have:
            raise SystemExit(f"corpus {a.corpus} lacks the extension chat {sorted(want - have)}")
    corpus_sha = cm["sha256"]
    if a.stage in ("main", "sonnet", "ext") and cm["repos"] != ["billing", "ingest", "inventory", "notify"]:
        raise SystemExit("the main, Sonnet and ext stages need the corpus of all four repos frozen")
    meter = meter_for(run_dir, a.stage, a.stub)
    model = "stub" if a.stub else MODELS[a.model]
    run_info = {"corpus": a.corpus, "corpus_sha256": corpus_sha, "model": model, "stage": a.stage,
                "manifest_sha256": manifest.build()["manifest_sha256"]}
    if (run_dir / "run.json").exists():  # a resume must use the same corpus, model, stage and task definitions
        prev = json.loads((run_dir / "run.json").read_text())
        if prev != run_info:
            raise SystemExit(f"run {a.run} was started with {prev}; refusing to resume with {run_info}")
    else:
        (run_dir / "run.json").write_text(json.dumps(run_info))
    chunks = corpus_mod.loads(blobs["chunks.jsonl"].decode())
    idx = Index(chunks)
    notes_idx = Index(distilled_index_chunks_from(blobs, chunks), embedder=idx.embedder)
    raw = FrozenRaw(json.loads(blobs["raw_blocks.json"]))
    providers = {"none": NoMemory(), "raw": raw, "retrieved": Retrieved(idx),
                 "distilled": Retrieved(notes_idx, budget_chars=3500), "pull": Pull(idx)}
    conds = a.conditions or list(CONDITIONS)
    tasks = [t for t in all_tasks() if t.repo in a.repos and (not a.families or t.family in a.families)
             and (not a.tasks or t.id in a.tasks)]
    done = done_episodes(run_dir)
    jobs = [(t, c, e) for e in range(1, a.epochs + 1) for t in tasks for c in conds
            if f"{t.id}__{c}__e{e}" not in done]

    def one(job):
        t, c, e = job
        client = s.client(EvalStub(t, pull=CONDITIONS[c] == "pull") if a.stub else None)
        r = run_episode(t, c, e, client, model, providers, run_dir, meter, Limits(), corpus_sha256=corpus_sha)
        print(json.dumps({k: r[k] for k in ("episode", "stop", "score", "calls", "cost")}), flush=True)
        return r

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, jobs))
    idx.close()
    print(json.dumps({"stage": "eval", "run": a.run, "episodes": len(jobs), "spent": round(meter.spent, 4)}))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("history", "distill", "freeze-corpus", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--corpus", required=True)
        p.add_argument("--stub", action="store_true")
        p.add_argument("--model", default="haiku", choices=sorted(MODELS))
        p.add_argument("--repos", nargs="*", default=["billing", "notify", "inventory", "ingest"])
        p.add_argument("--ext", action="store_true", help="the invisible-change extension (ext/ADDENDUM.md)")
        if name != "freeze-corpus":
            p.add_argument("--stage", choices=sorted(STAGE_CAPS), required=True)
        else:
            p.add_argument("--allow-leaks", help="JSON list of reviewed false-positive answer strings (an amendment)")
            p.add_argument("--force", action="store_true", help="replace an existing freeze (record an amendment)")
        if name == "eval":
            p.add_argument("--run", required=True)
            p.add_argument("--epochs", type=int, default=1)
            p.add_argument("--conditions", nargs="*", choices=sorted(CONDITIONS))
            p.add_argument("--families", nargs="*")
            p.add_argument("--tasks", nargs="*")
            p.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    if a.ext:
        os.environ["SMB_EXT"] = "1"  # read at call time by lessons(), chat_messages() and the task loader
        if a.cmd in ("history", "distill") or (a.cmd == "eval" and a.stage != "ext"):
            raise SystemExit("--ext adds no history: it freezes an extension corpus and runs eval in stage ext")
    elif getattr(a, "stage", None) == "ext":
        raise SystemExit("stage ext needs --ext")
    allowed = {"history": ("pilot", "history"), "distill": ("pilot", "history"), "eval": ("pilot", "main", "sonnet", "ext")}
    if a.cmd in allowed and a.stage not in allowed[a.cmd]:
        raise SystemExit(f"{a.cmd} runs in stage {' or '.join(allowed[a.cmd])}, not {a.stage}")
    if a.cmd in ("history", "distill") and ((a.stage == "pilot" and sorted(a.repos) != ["billing"])
                                            or (a.stage == "history" and "billing" in a.repos)):
        raise SystemExit("billing's history and distillation are the pilot stage; the other repos are the history stage")
    # one process per stage, so a stage's meter sees everything that stage books; a freeze holds the pilot and
    # history locks too, so no distillation writes notes while they are checked and hashed
    locks = []
    (RUNS / "locks").mkdir(parents=True, exist_ok=True)
    for stage in (("pilot", "history") if a.cmd == "freeze-corpus" else (a.stage,)):
        fh = open(RUNS / "locks" / f"{stage}.lock", "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(f"another process is running stage {stage}")
        locks.append(fh)
    if not a.stub:  # paid stages run on AC power (Amendment 1, item 4): sleep stalls requests until the deadline
        power = on_ac_power()
        if power is False:
            raise SystemExit("paid stages run on AC power only: plug in, keep the lid open, and run under caffeinate -s")
        if power is None:
            print(json.dumps({"warning": "can't read the power source (pmset); make sure the Mac is on AC power with the lid open"}))
    s = Session(a.stub, RUNS / "logs")
    try:
        {"history": cmd_history, "distill": cmd_distill, "freeze-corpus": cmd_freeze_corpus, "eval": cmd_eval}[a.cmd](a, s)
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
