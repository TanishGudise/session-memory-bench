"""Hybrid retrieval over memory chunks: BM25 top-50 and dense top-50 (bge-small-en-v1.5 cosine), fused by
reciprocal rank (k=60), returned in fused order until a character budget is spent. Ties break on chunk id, so
results are deterministic. The design follows post-cutoff-api-bench's docs retriever (same author).

The dense half runs in a separate interpreter (SMB_RETRIEVAL_PYTHON, with numpy/onnxruntime/tokenizers) via
smb/memory/embed_server.py; chunk embeddings are cached per corpus.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import threading
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from smb import sandbox
from smb.memory.corpus import Chunk
from smb.paths import ROOT

WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
# An interpreter with numpy, onnxruntime and tokenizers, and the bge-small-en-v1.5 ONNX export (see README).
RETRIEVAL_PYTHON = os.environ.get("SMB_RETRIEVAL_PYTHON", "")
EMBED_MODEL = os.environ.get("SMB_EMBED_MODEL", "")
CACHE = ROOT / ".cache" / "embeddings"


def tokens(text: str) -> list[str]:
    out = []
    for w in WORD.findall(text):
        lw = w.lower()
        out.append(lw)
        parts = [p for p in re.split(r"_|(?<=[a-z])(?=[A-Z])", w) if p]
        if len(parts) > 1:
            out.extend(p.lower() for p in parts)
    return out


class Embedder:
    """The embedding server runs sandboxed: no network, writes only under .cache/."""

    def __init__(self):
        if not (RETRIEVAL_PYTHON and EMBED_MODEL):
            raise SystemExit("set SMB_RETRIEVAL_PYTHON and SMB_EMBED_MODEL for the embedding half of retrieval")
        cache = ROOT / ".cache"
        cache.mkdir(parents=True, exist_ok=True)
        cmd = ["/usr/bin/sandbox-exec", "-p", sandbox.profile(cache),
               RETRIEVAL_PYTHON, "-I", str(ROOT / "smb/memory/embed_server.py"), EMBED_MODEL]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                     env={"PATH": "/usr/bin:/bin", "HOME": str(cache), "OMP_NUM_THREADS": "1"})
        self.lock = threading.Lock()
        ready = json.loads(self.proc.stdout.readline())
        assert ready.get("ready"), ready

    def embed(self, texts: list[str], query: bool = False) -> np.ndarray:
        with self.lock:
            self.proc.stdin.write(json.dumps({"texts": texts, "query": query}) + "\n")
            self.proc.stdin.flush()
            return np.array(json.loads(self.proc.stdout.readline())["vecs"], dtype=np.float32)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)


class Index:
    def __init__(self, chunks: list[Chunk], embedder: Embedder | None = None, dense: bool = True):
        self.chunks = chunks
        self.dense_enabled = dense
        self.embedder = embedder
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.dl = []
        for i, c in enumerate(chunks):
            tf = Counter(tokens(f"{c.repo} {c.where} {c.text}"))
            self.dl.append(sum(tf.values()))
            for t, n in tf.items():
                self.postings[t].append((i, n))
        self.avgdl = sum(self.dl) / max(1, len(self.dl))
        self.emb = self._embeddings() if dense else None

    def _embeddings(self) -> np.ndarray:
        key = hashlib.sha256("\n\x00".join(f"{c.id}\x01{c.text}" for c in self.chunks).encode()).hexdigest()[:16]
        path = CACHE / f"{key}.npy"
        if path.exists():
            return np.load(path)
        if self.embedder is None:
            self.embedder = Embedder()
        emb = self.embedder.embed([f"{c.repo} {c.where}\n{c.text}" for c in self.chunks]) if self.chunks else np.zeros((0, 384), np.float32)
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.npy")
        np.save(tmp, emb)
        os.replace(tmp, path)
        return emb

    def bm25(self, query: str, k: int = 50, k1: float = 1.2, b: float = 0.75) -> list[int]:
        n = len(self.chunks)
        scores: dict[int, float] = defaultdict(float)
        for t in set(tokens(query)):
            plist = self.postings.get(t)
            if not plist:
                continue
            idf = math.log(1 + (n - len(plist) + 0.5) / (len(plist) + 0.5))
            for i, tf in plist:
                scores[i] += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * self.dl[i] / self.avgdl))
        return [i for i, _ in sorted(scores.items(), key=lambda x: (-x[1], self.chunks[x[0]].id))[:k]]

    def dense(self, query: str, k: int = 50) -> list[int]:
        if self.embedder is None:
            self.embedder = Embedder()
        q = self.embedder.embed([query], query=True)[0]
        sims = self.emb @ q
        order = sorted(range(len(self.chunks)), key=lambda i: (-round(float(sims[i]), 5), self.chunks[i].id))
        return order[:k]

    def search(self, query: str, budget_chars: int) -> list[Chunk]:
        fused: dict[int, float] = defaultdict(float)
        rankings = [self.bm25(query)] + ([self.dense(query)] if self.dense_enabled else [])
        for ranking in rankings:
            for r, i in enumerate(ranking):
                fused[i] += 1 / (60 + r + 1)
        out, used = [], 0
        for i, _ in sorted(fused.items(), key=lambda x: (-round(x[1], 9), self.chunks[x[0]].id)):
            c = self.chunks[i]
            n = len(c.header()) + 1 + len(c.text)
            if used + n > budget_chars:
                if not out:
                    continue
                break
            out.append(c)
            used += n + 2
        return out

    def close(self) -> None:
        if self.embedder is not None:
            self.embedder.close()
