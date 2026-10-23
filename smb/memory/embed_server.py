"""bge-small-en-v1.5 (ONNX) embedding server, JSON lines on stdin/stdout. Runs in its own interpreter, which needs
numpy, onnxruntime and tokenizers. The embedding code follows post-cutoff-api-bench's retriever (same author).

  {"op": "embed", "texts": [...], "query": false}  ->  {"vecs": [[...], ...]}
"""

import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def main(model_dir: str) -> None:
    model = Path(model_dir)
    tok = Tokenizer.from_file(str(model / "tokenizer.json"))
    tok.enable_truncation(512)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1  # deterministic, and light on a shared machine
    opts.inter_op_num_threads = 1
    sess = ort.InferenceSession(str(model / "onnx" / "model.onnx"), sess_options=opts, providers=["CPUExecutionProvider"])
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        try:
            req = json.loads(line)
            texts = [(QUERY_PREFIX + t) if req.get("query") else t for t in req["texts"]]
            print(json.dumps({"vecs": embed(tok, sess, texts)}), flush=True)
        except Exception as exc:  # noqa: BLE001 - one bad request must not kill the server
            print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), flush=True)


def embed(tok, sess, texts):
    out = []
    if True:
        for i in range(0, len(texts), 32):
            encs = tok.encode_batch(texts[i:i + 32])
            width = max(len(e.ids) for e in encs)
            ids = np.zeros((len(encs), width), dtype=np.int64)
            mask = np.zeros_like(ids)
            for j, e in enumerate(encs):
                ids[j, : len(e.ids)] = e.ids
                mask[j, : len(e.ids)] = 1
            cls = sess.run(None, {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)})[0][:, 0, :]
            cls = cls / np.linalg.norm(cls, axis=1, keepdims=True)
            out.extend(np.round(cls, 6).tolist())
    return out


if __name__ == "__main__":
    main(sys.argv[1])
