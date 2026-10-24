# session-memory-bench

Which kind of memory from earlier agent sessions helps the next coding session, and when does it hurt?

Coding agents now run inside teams, and products that carry memory between their sessions are appearing. One common evaluation reverts a team's recent PRs and re-implements them with and without memory. It shows the net effect in the field, but it can't say which kind of memory produced it, whether the relevant memory was recalled at all, or how often memory made things worse. This benchmark is a controlled companion to that kind of replay:
- the memory is real agent transcripts, with scripted PR reviews and team chat;
- the lessons in it are labelled;
- grading is by hidden tests only, with no LLM judge.

The design, metrics and stop rules were registered before any model call: [PREREGISTRATION.md](PREREGISTRATION.md). Each later run was preceded by a dated amendment, and the extension has its own addendum ([ext/ADDENDUM.md](ext/ADDENDUM.md)). Amendment 3, after the main run, records a deviation and one task exclusion under the registered defect rule.

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
   | c | retrieved | hybrid BM25 + embedding search over all sessions and chat, queried with the prompt, the previous assistant turn and repo/branch (what a memory hook sees when a prompt is submitted), injected with the prompt. Memory is injected once, at the session's first prompt, so the previous turn is empty |
   | d | distilled | notes distilled from each session, plus the team chat, retrieved the same way |
   | f | pull | nothing injected; the agent can call `search_memory` |
   | g | oracle | the exact lesson, the ceiling |

5. **Grading.** Hidden tests tagged `func` (the feature works), `lesson` (it follows the team's rule) and `diag` (diagnostics such as "followed the old rule", not scored). Each failure is classified from the lesson labels and the test kinds: *not retrieved*, *retrieved but not applied*, *followed the old rule*, *followed the other repo's rule*, or *other*.
   - A chunk carries a lesson when it contains at least 60 consecutive characters of the sentence that states the rule.
   - Distilled notes carry the lessons a person assigned to them before the run.
   - Stale and superseded tasks add *old rule recalled, not followed* and *current rule recalled, not applied*.
   - Episodes that were never graded are reported as *not graded* with their status (for example a missing module, or a tampered run). Ones that didn't finish are reported as *unfinished* with their stop reason.

## Results

Claude Haiku 5.5 throughout. Main run: 960 episodes ([RESULTS.md](RESULTS.md)). Invisible-change extension: 300 episodes ([EXT_RESULTS.md](EXT_RESULTS.md), registered in [ext/ADDENDUM.md](ext/ADDENDUM.md)). Pilot: [PILOT.md](PILOT.md). Total API spend: $4.61. The Sonnet cross-check was skipped.

- **Memory strongly helps.** On tasks that need a lesson from earlier work (70 runs per condition), the agent solved 14% with no memory, 41% with retrieved snippets, 63% with a search tool, 79% with distilled notes and 99% with raw transcripts. All four registered benefit tests hold after Holm correction.
- **Hook-shaped retrieval over transcript snippets missed most lessons.** The query is the prompt plus repo/branch at a session's first prompt. Over transcript snippets it held the needed lesson 25% of the time; the same query over distilled notes held it 88%, and raw transcripts held it 100%. Clear misses (35 of 110) fell on six lessons and were the same every epoch. On the same task and epoch, the search tool recovered the lesson and passed in 24 of the 35.
- **Stale memory didn't hurt when the code showed the change.** The agent's own reads showed it in 238 of 240 runs, and no run followed the old rule.
- **It did hurt when the change was only in a later chat message** (extension). Transcript snippets followed the old rule in 20 of 50 runs (two of the five tasks, every epoch), and distilled notes in 10 of 50 (one task, every epoch); raw transcripts and the search tool in none. Every old-rule run had recalled only the old decision. When both decisions were recalled, the agent followed the newer one in 137 of 139 runs.
- **Cost.** Distilled notes were the cheapest effective memory per solved task ($0.0038 on the memory tasks, against $0.0168 with no memory). Raw transcripts cost about 2.2× as much per solve, and they only fit because these repos' histories are 29k-35k tokens.

**Caveat on the retrieved condition.** It tests the *query shape* of hook-based injection (the submitted prompt and repo/branch, at a session's first prompt) with this repo's own retriever: BM25 and bge-small-en-v1.5 fused by reciprocal rank, with a 7,000-character budget. It does not test any product's server-side retrieval or LLM ranking, which may recall much more.

The paid stages were capped at $17.50 in total (extension: $3).

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
python scripts/validate_ext.py                          # extension gate (G1-ext)
python scripts/manifest.py --freeze
python scripts/paid.py freeze-corpus --ext --corpus ext1 --repos billing notify inventory ingest   # ext1 = copies of run1's sessions and notes
python scripts/paid.py eval --ext --stage ext --run ext --corpus ext1 --epochs 10
python scripts/analyze_ext.py runs/eval/ext
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

## Data

`runs/` (history transcripts, distilled notes and labels, frozen corpora, every episode's transcript and result, spend ledgers) is not in git. It is published as a separate data release, `runs.tar.gz`.

## Limits

- one fictional organisation and one draw of history sessions;
- small families (14 memory-only, 8 stale or superseded);
- small synthetic repos;
- a candidate that deliberately forges a test run could still pass; static flags and hand checks are the backstop;
- the graded code shares a process with the hidden tests (editable paths are allowlisted, the JUnit set is checked exactly, and suspicious code is flagged for hand-checking).
