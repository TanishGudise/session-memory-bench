# Pre-registration

Question: which kind of memory from earlier agent sessions helps the next coding session, and when does it hurt?

Registered 2026-10-22, before any model call. Changes after this point are listed under Amendments with their date and reason; nothing above that section changes.

## 1. Material

- **Repos.** Four small repositories of one fictional company: `billing`, `notify`, `ingest` (Python) and `inventory` (TypeScript run by Node's type stripping). Each is a base tree plus dated steps (`repos/<repo>/steps/MMDD-<id>/`): the changes earlier sessions merged, and one later change that no session recorded (`U1`). The evaluation starts from the state with every step applied ("main").
- **History.** 26 earlier tasks (`history/<repo>.yaml`), dated 2026-08-04 to 2026-09-24. The agent works each one, then gets a scripted PR review and one revision round: comments marked `always` are always posted; a `failed:<check>` comment is posted only when that check (`history/checks/`) fails on the first submission. Four team-chat messages (`history/chat.yaml`) complete the memory. Lessons enter memory only through these texts: tickets, review comments and chat. What lands on main is the reference step, not the agent's diff.
- **Memory corpus.** The history transcripts (Claude Code session-JSONL shape), produced once by the same model and harness as the main run, plus the chat messages. The corpus, its chunks and its notes are frozen (hashes in the manifest) before any evaluation episode.
- **Tasks.** 32 evaluation tasks (`tasks/`), phrased the way a teammate asks (the interface to build, no hints about the lesson). Families:
  - **M** (14), memory-only: the rule appears nowhere in main (checked by `lessons.yaml` evidence patterns; 0 hits) and only in earlier sessions, reviews or chat.
  - **D** (4), discoverable: main's code already follows the convention.
  - **S-u** (4), stale and unrecorded: memory holds an old rule; main shows the new one (a deprecation, changelog and code), and no session recorded the change.
  - **S-s** (4), superseded: memory holds the old rule and the later session that changed it; main shows the new one.
  - **X** (2), cross-repo: another repo's memory holds the opposite convention; this repo's code shows its own.
  - **C** (4), control: memory is irrelevant.
- **Grading.** Hidden tests only, no LLM judge. Test names carry a kind: `func` (does the feature work), `lesson` (does it follow the lesson), `diag` (diagnostics such as "followed the old rule"; never scored). An episode passes when every `func` and `lesson` test passes. The candidate tree is main plus only the task's editable paths from the agent's workspace (never `conftest.py`, `pytest.ini`, `sitecustomize.py`, `package.json` and similar). Hidden tests run in a separate sandboxed process (no network, writes only in the grading directory). The JUnit test set must equal the hidden file's test set exactly. Graders run with `TZ=America/Los_Angeles`.

## 2. Conditions

Same model, system prompt, task prompt, tools and budgets in every condition; only memory differs. Memory is appended to the task prompt in a `<team-memory>` block whose wording is fixed in `smb/memory/provider.py`.

| id | condition | what the agent gets |
|---|---|---|
| a | none | no memory |
| b | raw | this repo's session transcripts, newest first, whole sessions only, plus all chat messages, up to **40,000 tokens** counted by the Messages API `count_tokens` endpoint for the run's model at corpus freeze. Tool inputs are clipped to 2,000 characters and tool results to 800 (task, review and agent text verbatim). This keeps every request under the 100,000-token long-prompt price tier together with the per-request guard (section 3). |
| c | retrieved | chunks from an org-wide index (all four repos and chat), hybrid BM25 + bge-small-en-v1.5 fused by reciprocal rank, up to 7,000 characters, each with date, repo, branch or channel, kind and author. The query is the submitted prompt + the previous assistant turn + `repo: <repo> branch: <branch>`, the payload a memory hook receives when a prompt is submitted; at the start of a session the previous assistant turn is empty. Injected once, with the prompt. |
| d | distilled | notes distilled once per history session by the run's model with the fixed prompt in `smb/memory/distill.py` (at most 8 per session, dated), retrieved by the same method and query, up to 3,500 characters. |
| f | pull | nothing injected; a `search_memory(query)` tool over the same index as c (7,000 characters per call); the system prompt gains one sentence naming the tool. |
| g | oracle | the exact current lesson notes for the task (`lessons.yaml`), the ceiling and a solvability check |

## 3. Agent and budgets

A minimal loop on the Messages API (`smb/agent.py`). Tools: `list_dir`, `read_file`, `search_code`, `write_file`, `replace_in_file`, `run_tests` (the visible suite or a path, sandboxed, `TZ=America/Los_Angeles`), `finish`, and `search_memory` in f. No shell. Per episode: at most 30 model calls, `max_tokens` 8,000, 10 minutes wall clock, prompt caching on. A request whose estimated prompt exceeds 95,000 tokens is not sent and the episode ends `context_limit`. Effort is the model's default.

- Main run: `claude-haiku-5-5`, all 32 tasks × 6 conditions × **3 epochs** (576 episodes). If the pilot projects this above its $12 cap, the main run uses 2 epochs; that choice is recorded as a dated amendment before the main run starts.
- Cross-check: `claude-sonnet-5-5` on the 8 S tasks in a and c, then d if the $3 cap allows, 1 epoch.
- History and distillation use the main run's model.

## 4. Outcomes and hypotheses

Unit: one episode (task × condition × epoch). Outcome: pass (1) or fail (0). Episodes that end in `cap` or a harness `error` are excluded from both sides of a pair and reported. `context_limit`, `call_limit`, `wall_clock`, `no_finish` and `refusal` count as fails.

Tests: exact McNemar on outcomes paired by (task, epoch); Holm within each family, α = 0.05. Robustness: the paired difference with a 95% task-cluster bootstrap interval (10,000 resamples, seed 0).

**Family A, benefit (M tasks), Holm over 4:**
- A1: c passes more often than a (one-sided).
- A2: d vs c (two-sided).
- A3: b vs c (two-sided).
- A4: f vs c (two-sided).

**Family B, harm (co-primary; S tasks = S-u ∪ S-s), Holm over 4:**
- B1 to B4: each of b, c, d and f passes less often than a (one-sided).
- Reported with each condition's failure rate on S tasks (Wilson 95%) and the failure breakdown below.

**Failure breakdown (exact, from labels and test kinds):**
- M, D and X tasks: *not retrieved* (some needed lesson is in no recalled item), *retrieved, not applied* (every needed lesson recalled, a `lesson` test failed), *other* (lessons recalled and `lesson` tests pass, a `func` test failed). For b, "recalled" means the lesson's authored text is inside the injected block; for c and f, a recalled chunk carries it (span label: at least 60 consecutive characters of the ticket, review comment or chat text that carries the lesson); for d, the note's frozen hand label (section 5).
- S tasks: *followed the old rule* (a `diag` test passed), *current rule recalled, not applied*, *other*.
- X tasks: *followed the other repo's rule* (`diag` passed).

**Write-up rule:** if c and g both pass at least 90% of M episodes (accuracy saturates), the write-up leads with Family B (harm) and cost. Otherwise Families A and B are co-headlines.

**Secondary (descriptive, no correction):**
- pass rates by family × condition (Wilson);
- tokens, dollars, calls and wall clock per episode and per solved task, D tasks against a (a token-savings claim lives here), and b's tokens and dollars per solved task;
- read and search calls before the first edit;
- X contamination rate, and C distraction (pass rate and tokens against a);
- retrieval precision (share of recalled chunks whose source is a labelled source of a needed lesson) and lesson recall, for the org-wide index used in c and f and, offline, a repo-filtered index;
- f: share of episodes that searched at all, and searches per episode;
- S-s: old against new rule followed;
- the Sonnet cross-check.

## 5. Labels

- Which session, review comment or chat message carries which lesson is fixed in `history/*.yaml` and `lessons.yaml` before any run.
- Chunk span labels are computed from those texts.
- Notes distilled by a model paraphrase, so after distillation and before any evaluation episode, every note is labelled by hand with the lessons it states, using the definitions in `lessons.yaml`. The labels are frozen in `notes_labels.json`. The pattern labels in `lessons.yaml` are reported next to them as an automated cross-check.

## 6. Gates and stop rules

- **G1 ($0, before any model call):**
  - every task's solution matrix holds and is identical over 5 repeats under 8 concurrent graders: oracle 1 with no diagnostic firing; no-op 0; visible-only 0 with a lesson test failing; stale and other-repo solutions 0 with their diagnostic firing;
  - every solution passes the visible suite under `TZ=UTC`;
  - main and every history start state pass their visible suites under `TZ=UTC`;
  - history checks behave as listed in `scripts/validate.py`;
  - memory-only lessons have no evidence in main;
  - no oracle line and no hidden-test string literal of 12+ characters appears in any memory text;
  - the stub end-to-end run is clean (no-memory stub 0 on M and D; oracle stub passes every task).
- **G2 (pilot on billing, ≤ $1.50):** on billing's M tasks, g ≥ 70% and a ≤ 30%; on billing's C and D tasks together, a passes at least 1 of 2. Otherwise the tasks are redesigned before any further spend, and the redesign is an amendment.
- **G3 (spend):**
  - every call reserves its worst case before it is sent (1 token per character of input at the higher of the input and cache-write prices, plus the full `max_tokens` of output);
  - stage caps: pilot $1.50, history and distillation $1.00, main $12, Sonnet $3; total $17.50 of a $20 budget;
  - a stage stops at its cap, and episodes stopped by the cap are reported, not scored.
- **G4 (hand checks):**
  - every a pass on an M task;
  - every S task where a and c disagree;
  - every episode flagged by the grader's tamper check;
  - a random 10% of the rest (seed 0).

  A grader or task defect found this way is fixed, every condition is re-graded the same way (log in the run directory), and the task is fixed or excluded with the reason.
- **Leakage:** re-checked on the frozen corpus before the main run: no oracle line or hidden-test literal appears in any chunk or note.

## 7. Known limits

- One draw of history sessions.
- One fictional organization.
- Small task counts: M 14, S 8.
- Synthetic repos of about 1,000 lines each.
- Haiku is not the model most production agents run; the Sonnet cross-check is small.
- Graded code shares a process with the hidden tests; a determined candidate could tamper with the run. The grader allowlists editable paths, checks the exact JUnit set and flags suspicious references; flagged passes are hand-checked.

## Amendments

(none yet)
