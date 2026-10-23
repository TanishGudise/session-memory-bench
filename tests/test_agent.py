from types import SimpleNamespace

from smb.agent import Episode, Limits, tool_specs
from smb.meter import Meter
from smb.tools import Workspace
from smb.transcript import TranscriptWriter, read


class Scripted:
    def __init__(self, steps):
        self.steps = list(steps)
        self.messages = SimpleNamespace(create=self.create)
        self.seen = []

    def create(self, **kw):
        self.seen.append(kw)
        blocks, stop = self.steps.pop(0)
        return SimpleNamespace(content=blocks, stop_reason=stop,
                               usage=SimpleNamespace(input_tokens=100, output_tokens=10, cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0))


def _ep(tmp_path, steps, **kw):
    (tmp_path / "ws").mkdir()
    client = Scripted(steps)
    ep = Episode(client=client, model="stub", system="sys", tools=tool_specs(), ws=Workspace(tmp_path / "ws", "py"),
                 meter=Meter(0.0), transcript=TranscriptWriter(tmp_path / "t.jsonl", "s", "/w", "b"), **kw)
    return ep, client


def tu(name, i, **inp):
    return {"type": "tool_use", "id": f"t{i}", "name": name, "input": inp}


def test_tool_errors_are_returned_and_finish_stops(tmp_path):
    ep, client = _ep(tmp_path, [([tu("read_file", 1, path="../x"), tu("write_file", 2, path="a.py", content="x=1")], "tool_use"),
                                ([tu("finish", 3, summary="done")], "tool_use")])
    assert ep.user_turn("task") == "finished"
    results = ep.messages[2]["content"]
    assert results[0]["is_error"] and "not allowed" in results[0]["content"]
    assert (tmp_path / "ws" / "a.py").read_text() == "x=1"
    assert ep.summary == "done" and ep.calls == 2 and ep.first_edit_call == 1
    assert client.seen[0]["cache_control"] == {"type": "ephemeral"}
    recs = read(tmp_path / "t.jsonl")
    assert [r["type"] for r in recs] == ["user", "assistant", "user", "assistant", "user"]
    assert recs[1]["parentUuid"] == recs[0]["uuid"]


def test_nudges_then_gives_up(tmp_path):
    text = [{"type": "text", "text": "thinking aloud"}]
    ep, _ = _ep(tmp_path, [(text, "end_turn")] * 3)
    assert ep.user_turn("task") == "no_finish"


def test_context_guard(tmp_path):
    ep, client = _ep(tmp_path, [], limits=Limits(prompt_guard=10))
    assert ep.user_turn("x" * 100) == "context_limit" and client.seen == []


def test_call_limit(tmp_path):
    steps = [([tu("list_dir", i)], "tool_use") for i in range(5)]
    ep, _ = _ep(tmp_path, steps, limits=Limits(max_calls=3))
    assert ep.user_turn("task") == "call_limit" and ep.calls == 3


def test_a_call_that_never_returns_is_abandoned_booked_and_retried(tmp_path, monkeypatch):
    import threading

    import pytest

    from smb import agent
    monkeypatch.setattr(agent, "DEADLINE_SLACK", 0.2)
    monkeypatch.setattr(agent, "RETRY_SLEEP", (0.0, 0.0))
    stuck = threading.Event()

    def create(**kw):  # a read that never ends, like a socket that keeps receiving bytes
        stuck.wait(30)
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    meter = Meter(cap_usd=1.0, ledger_path=tmp_path / "spend.jsonl", stage="t")
    with pytest.raises(agent.CallDeadline):
        agent.metered_create(client, meter, "claude-haiku-5-5", "sys", [{"role": "user", "content": "hi"}], [], 100, timeout=0.1)
    stuck.set()
    lines = (tmp_path / "spend.jsonl").read_text().splitlines()
    assert len(lines) == agent.API_ATTEMPTS and all('"worst_case": true' in l for l in lines)  # each may have been billed
    assert meter.reserved == 0
