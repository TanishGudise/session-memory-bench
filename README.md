# session-memory-bench

Which kind of memory from earlier agent sessions helps the next coding session, and when does it hurt?

Coding agents now run inside teams, and products that carry memory between their sessions are appearing. The usual evaluation reverts a team's recent PRs and re-implements them with and without memory. It shows the net effect in the field, but it can't say which kind of memory produced it, whether the relevant memory was recalled at all, or how often memory made things worse. This benchmark is a controlled companion to that kind of replay:
- the memory is real agent transcripts and PR reviews;
- the lessons in it are labelled;
- grading is by hidden tests only, with no LLM judge.

The design, metrics and stop rules were registered before any model call: [PREREGISTRATION.md](PREREGISTRATION.md).

## How it works

1. **A small organisation with a past.** Four small repositories (roughly 280–620 lines each, tests included) evolve through dated steps ([repos/](repos)). `billing`, `notify` and `ingest` are Python; `inventory` is TypeScript run directly by Node.
2. **Earlier sessions.** 26 earlier tasks ([history/](history)) are worked by the same agent, then get a scripted PR review and one revision round. Lessons enter memory the way they do at a company:
   - an incident ticket, such as a gateway that timed out after it had already captured the charge;
   - a review comment, such as never renaming a column in one migration;
   - a closed PR, or an investigation that ended in "it's the known flake";
   - a chat message, such as a warehouse being returns-only.

   Their transcripts, plus team chat, are the memory corpus. It is frozen and hashed before any evaluation episode.
3. **Later tasks.** 32 tasks ([tasks/](tasks)), phrased the way a teammate asks:

   | family | n | what it tests |
   |---|---|---|
   | M, memory-only | 14 | the rule is stated only in earlier sessions, reviews or chat (checked: no line of the code matches the lesson's evidence patterns) |
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
   | d | distilled | notes distilled from each session, plus the team chat, retrieved the same way |
   | f | pull | nothing injected; the agent can call `search_memory` |
   | g | oracle | the exact lesson, the ceiling |

5. **Grading.** Hidden tests tagged `func` (the feature works), `lesson` (it follows the team's rule) and `diag` (diagnostics such as "followed the old rule", not scored). Each failure is classified from the lesson labels and the test kinds: *not retrieved*, *retrieved but not applied*, *followed the old rule*, *followed the other repo's rule*, or *other*.
   - A chunk carries a lesson when it contains at least 60 consecutive characters of the sentence that states the rule.
   - Distilled notes carry the lessons a person assigned to them before the run.
   - Stale and superseded tasks add *old rule recalled, not followed* and *current rule recalled, not applied*.
   - Episodes that were never graded are reported as *not graded* with their status (for example a missing module, or a tampered run). Ones that didn't finish are reported as *unfinished* with their stop reason.

## Results

The pilot (`PILOT.md`) and the main run (`RESULTS.md`; 960 episodes, 5 epochs) are done, at $3.64 in total. The Sonnet check has not run yet. The paid stages are pilot, history, main run and a Sonnet check, capped at $17.50 in total.

## Validation ($0)

`python scripts/validate.py` (report in [validation/report.json](validation/report.json)) checks:
- every task's solution matrix, identical over 5 repeats under concurrent graders:
  - the oracle passes;
  - doing nothing, ignoring the lesson, following the old rule and following the other repo's rule all fail;
  - the last two also trip their diagnostic;
- every solution passes the visible test suite, so the visible tests don't give the lesson away;
- every history session's start state and checks;
- that no line of the eval-time code matches a memory-only lesson's evidence patterns;
- that no answer string (task-specific oracle lines and hidden-test literals, as defined in PREREGISTRATION.md) appears in the tickets, reviews and chat. The same check runs on the agents' own transcripts, notes and raw blocks when the corpus is frozen.

`python scripts/stub_e2e.py` runs every stage end to end with stub models and no network. The stages are history, distillation, freeze, and all 32 tasks × 6 conditions.

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
- `scripts/`: `validate.py`, `stub_e2e.py`, `paid.py`, `label_notes.py`, `analyze.py`, `manifest.py`

## Running

Requirements:
- Python 3.13 with `anthropic`, `pytest`, `pyyaml`, `numpy`;
- Node 26 (no packages);
- macOS `sandbox-exec`;
- for the embedding half of retrieval, set two environment variables: `SMB_RETRIEVAL_PYTHON` (an interpreter with `numpy`, `onnxruntime` and `tokenizers`) and `SMB_EMBED_MODEL` (the `bge-small-en-v1.5` ONNX export);
- workspaces live under `SMB_WORK` (default `~/.smb-work`);
- the base Python and Node interpreters must live outside the home directory (e.g. python.org or Homebrew installs), because sandboxed code can't read under `$HOME`.

```
python -m pytest                       # harness tests
python scripts/stub_e2e.py             # $0 end-to-end run
python scripts/validate.py             # G1 validation
python scripts/manifest.py --freeze    # freeze before any paid run
python scripts/paid.py history --stage pilot --corpus run1 --repos billing
python scripts/paid.py distill --stage pilot --corpus run1 --repos billing
python scripts/label_notes.py run1                     # then review the labels by hand
python scripts/paid.py freeze-corpus --corpus run1 --repos billing
python scripts/paid.py eval --stage pilot --run pilot --corpus run1 --repos billing --epochs 1
python scripts/paid.py eval --stage pilot --run pilot --corpus run1 --repos notify inventory ingest --families M --conditions a g
python scripts/paid.py history --stage history --corpus run1 --repos notify inventory ingest
python scripts/paid.py distill --stage history --corpus run1 --repos notify inventory ingest
python scripts/label_notes.py run1                     # then review the new labels by hand
python scripts/paid.py freeze-corpus --corpus run1 --repos billing notify inventory ingest
python scripts/paid.py eval --stage main --run main --corpus run1 --epochs 5
python scripts/analyze.py runs/eval/main --corpus runs/history/run1
python scripts/analyze.py runs/eval/pilot --corpus runs/history/run1
```

Paid stages read the API key from a gitignored `.env`. Run them on AC power, with the lid open and system sleep prevented (for example `caffeinate -s python scripts/paid.py ...`): sleep stops the HTTP timeout's clock, so a request waits until the wall-clock deadline after the wake. Paid stages refuse to start on battery.
- All model traffic goes through a loopback proxy that allows only the API host, and the run process can open loopback connections only.
- Agent code, graders and the embedder run sandboxed. They get no network, and they can't read file contents under the home directory (the benchmark, its git history, other workspaces) or the shared temp dirs. The exceptions are their own directory, the project's Python environment and, for the embedder, its interpreter, model and server script.
- The agent's file tools never follow or list symbolic links, even ones inside the workspace.
- Every grading run includes tests that must fail, so a blanket patch of an assertion helper or `pytest.raises` is caught.
- The runner's summary (pytest's single final summary line, or node's final TAP block) must agree with the JUnit report.
- Some other tampering is flagged by static patterns and checked by hand.
- A determined candidate could still forge a run (see Limits).
- Every request, including every retry, reserves its worst-case cost against its stage's cap before it is sent. A request that may have been billed without returning usage is booked at that worst case.

## Limits

- one fictional organisation and one draw of history sessions;
- small families (14 memory-only, 8 stale or superseded);
- small synthetic repos;
- a candidate that deliberately forges a test run could still pass; static flags and hand checks are the backstop;
- the graded code shares a process with the hidden tests (editable paths are allowlisted, the JUnit set is checked exactly, and suspicious code is flagged for hand-checking).
