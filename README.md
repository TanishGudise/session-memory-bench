# session-memory-bench

Which kind of memory from earlier agent sessions helps the next coding session, and when does it hurt?

Coding agents now run inside teams, and products that carry memory between their sessions are appearing. The usual evaluation reverts a team's recent PRs and re-implements them with and without memory. It shows the net effect in the field, but it can't say which kind of memory produced it, whether the relevant memory was recalled at all, or how often memory made things worse. This benchmark is a controlled companion to that kind of replay:
- the memory is real agent transcripts and PR reviews;
- the lessons in it are labelled;
- grading is by hidden tests only, with no LLM judge.

The design, metrics and stop rules were registered before any model call: [PREREGISTRATION.md](PREREGISTRATION.md).

## How it works

1. **A small organisation with a past.** Four repositories (`billing`, `notify`, `ingest` in Python; `inventory` in TypeScript run directly by Node) evolve through dated steps ([repos/](repos)).
2. **Earlier sessions.** 26 earlier tasks ([history/](history)) are worked by the same agent, then get a scripted PR review and one revision round. Lessons enter memory the way they do at a company:
   - an incident ticket ("the gateway timed out after it had already captured the charge");
   - a review comment ("we never rename a column in one migration");
   - a closed PR, an investigation that ended in "that's the known flake";
   - a chat message ("RNO is a returns-only location").

   Their transcripts, plus team chat, are the memory corpus.
3. **Later tasks.** 32 tasks ([tasks/](tasks)), phrased the way a teammate asks:

   | family | n | what it tests |
   |---|---|---|
   | M, memory-only | 14 | the rule exists only in earlier sessions, reviews or chat (checked: no trace in the code) |
   | D, discoverable | 4 | the code already shows the convention; memory can only save exploration |
   | S-u, stale | 4 | memory holds an old rule; a later change nobody recorded in a session replaced it, and the code shows the new one |
   | S-s, superseded | 4 | memory holds the old rule and the later session that changed it |
   | X, cross-repo | 2 | another repo's memory holds the opposite convention |
   | C, control | 4 | memory is irrelevant |

4. **Memory conditions.** Same agent, prompt, tools and budgets; only memory differs:

   | id | condition | memory |
   |---|---|---|
   | a | none | nothing |
   | b | raw | this repo's transcripts, newest first, whole sessions, plus chat, within 40k tokens |
   | c | retrieved | hybrid BM25 + embedding search over all sessions and chat, queried with the prompt, the previous assistant turn and repo/branch (what a memory hook sees when a prompt is submitted), injected with the prompt |
   | d | distilled | notes distilled from each session, retrieved the same way |
   | f | pull | nothing injected; the agent can call `search_memory` |
   | g | oracle | the exact lesson, the ceiling |

5. **Grading.** Hidden tests tagged `func` (the feature works), `lesson` (it follows the team's rule) and `diag` (diagnostics such as "followed the old rule", not scored). Every failure is classified exactly, from the labels and the test kinds: *not retrieved*, *retrieved but not applied*, *followed the old rule*, *followed the other repo's rule*, or *other*.

## Results

Not run yet. The paid stages are pilot, history, main run and a Sonnet check, capped at $17.50 in total.

## Validation ($0)

`python scripts/validate.py` (report in [validation/report.json](validation/report.json)) checks:
- every task's solution matrix, identical over 5 repeats under 8 concurrent graders: the oracle passes; doing nothing, ignoring the lesson, following the old rule and following the other repo's rule all fail, and each failure trips the matching diagnostic;
- every solution passes the visible test suite, so the visible tests don't give the lesson away;
- every history session's start state and checks;
- that memory-only lessons leave no trace in the code;
- that no oracle line or hidden-test string appears in any memory text.

`python scripts/stub_e2e.py` runs every stage end to end with stub models, with no network.

## Layout

- `repos/<repo>/base`, `repos/<repo>/steps/MMDD-<id>/`: repo states
- `history/<repo>.yaml`, `history/chat.yaml`, `history/checks/`: earlier tasks, reviews, chat, review triggers
- `lessons.yaml`: every lesson, its sources and its oracle note
- `tasks/<id>/`: `task.yaml`, `hidden/`, `solutions/{oracle,visible_only,stale_rule,other_repo}/`
- `smb/`:
  - `agent.py`, `tools.py`: the minimal agent loop and its tools
  - `history.py`: history sessions with the scripted reviewer
  - `memory/`: corpus, labels, retriever, conditions, distillation
  - `grade.py`, `sandbox.py`: grading and sandboxing
  - `meter.py`, `proxy.py`, `netguard.py`: spend cap and network guard
- `scripts/`: `validate.py`, `stub_e2e.py`, `paid.py`, `analyze.py`, `manifest.py`

## Running

Requirements:
- Python 3.13 with `anthropic`, `pytest`, `pyyaml`, `numpy`;
- Node 26 (no packages);
- macOS `sandbox-exec`;
- for the embedding half of retrieval, a second interpreter with `numpy`, `onnxruntime` and `tokenizers` (`SMB_RETRIEVAL_PYTHON`), and the `bge-small-en-v1.5` ONNX export (`SMB_EMBED_MODEL`).

```
python -m pytest                       # harness tests
python scripts/stub_e2e.py             # $0 end-to-end run
python scripts/validate.py             # G1 validation
python scripts/manifest.py --freeze    # freeze before any paid run
python scripts/paid.py history --corpus run1 --repos billing --cap 0.50
python scripts/paid.py eval --run pilot --corpus run1 --repos billing --epochs 1 --cap 1.50
python scripts/analyze.py runs/eval/pilot --corpus runs/history/run1
```

Paid stages read the API key from a gitignored `.env`. All model traffic goes through a loopback proxy that allows only the API host. The run process can open loopback connections only. Agent code, graders and the embedder run sandboxed with no network. Every call reserves its worst-case cost against a hard cap before it is sent.

## Limits

- one fictional organisation and one draw of history sessions;
- small families (14 memory-only, 8 stale or superseded);
- repos of about 1,000 lines;
- the graded code shares a process with the hidden tests (editable paths are allowlisted, the JUnit set is checked exactly, and suspicious code is flagged for hand-checking).
