from smb.memory.corpus import history_specs
from smb.memory.provider import FrozenRaw, build_raw_blocks, estimate_tokens
from smb.transcript import TranscriptWriter


def _corpus(tmp_path):
    for sid, spec in history_specs().items():
        tw = TranscriptWriter(tmp_path / sid / "transcript.jsonl", sid, "/w", spec["branch"])
        tw.add("user", [{"type": "text", "text": spec["ticket"]}])
        tw.add("assistant", [{"type": "text", "text": "x" * 4000}])
        tw.add("user", [{"type": "text", "text": "Review from " + spec["author"] + ":\n\n" + "\n\n".join(r["text"] for r in spec["review"])}])
    return tmp_path


def test_cap_keeps_whole_newest_sessions(tmp_path):
    corpus = _corpus(tmp_path)
    full = build_raw_blocks(corpus, estimate_tokens, cap_tokens=10**9)
    capped = build_raw_blocks(corpus, estimate_tokens, cap_tokens=3500)
    b = capped["billing"]
    assert full["billing"]["sessions_skipped"] == [] and b["tokens"] <= 3500
    assert 0 < len(b["sessions_included"]) < len(full["billing"]["sessions_included"])
    newest_first = full["billing"]["sessions_included"]
    assert b["sessions_included"] == newest_first[: len(b["sessions_included"])]
    assert b["sessions_skipped"] == newest_first[len(b["sessions_included"]):]
    for sid in b["sessions_skipped"]:
        assert f"{history_specs()[sid]['branch']} · " not in b["block"]
    r = FrozenRaw(capped).recall("p", "", {"repo": "billing", "branch": "b"})
    assert r.block == b["block"] and r.meta["sessions_included"] == b["sessions_included"]
