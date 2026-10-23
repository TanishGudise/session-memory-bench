# Pre-registration

Question: which kind of memory from earlier agent sessions helps the next coding session, and when does it hurt?

Registered 2026-10-22, before any model call. Changes after the first model call are listed under Amendments with their date and reason; nothing above that section changes after that point.

## 1. Material

- **Repos.** Four small repositories of one fictional company: `billing`, `notify` and `ingest` (Python), and `inventory` (TypeScript, run by Node's type stripping). Each is between roughly 280 and 620 lines including tests.
  - A repo is a base tree plus dated steps (`repos/<repo>/steps/MMDD-<id>/`): the changes earlier sessions merged, plus one later change that no session recorded (`U1`).
  - The evaluation starts from the state with every step applied ("main").
- **History.** 26 earlier tasks (`history/<repo>.yaml`), dated 2026-08-04 to 2026-09-24.
  - The agent works each task, then gets a scripted PR review and one revision round.
  - Comments marked `always` are always posted. A `failed:<check>` comment is posted only when that check (`history/checks/`) fails on the first submission.
  - Four team-chat messages (`history/chat.yaml`) complete the memory.
  - Lessons enter memory only through these texts.
  - What lands on main is the reference step, not the agent's diff.
- **Memory corpus.** The history transcripts (in the Claude Code session-JSONL shape), produced once by the same model and harness as the main run, plus the chat messages.
  - `scripts/paid.py freeze-corpus` writes the chunks and condition b's blocks, checks the distilled notes and their hand labels (written earlier by distillation and `scripts/label_notes.py`), runs the leakage check, and writes a hash of every file to `CORPUS_MANIFEST.json`.
  - This happens before any evaluation episode. Eval refuses to run if a file no longer matches. A freeze can't be silently replaced: every check runs before anything is swapped in, and a re-freeze may only add repos while the frozen sessions, notes and note labels stay unchanged. Anything else needs `--force` and an amendment. A run directory refuses to resume under a different corpus, model, stage or task manifest.
  - A history session that ends on a spend cap or an API error, or whose checks can't be graded (snapshot over budget, timeout, `no_junit`, `junit_mismatch`, `tampered`), is not kept: it is run again, and the re-run is a fresh draw of that session. Every discarded attempt gets a numbered line in `attempts.jsonl` in the session's directory, with its cause; an attempt that was killed, or whose line could not be written, gets one when the session is next run. Before a re-run, the earlier transcript is renamed `attempt-<n>.transcript.jsonl`. `analyze.py --corpus` lists the discarded attempts, and the write-up reports how many there were and why.
  - The pilot freezes a billing-only corpus: billing's 7 sessions plus chat. The other 19 sessions are added to the same corpus directory afterwards; billing's sessions are not re-run. The full corpus of all four repos is frozen, and its hash recorded as an amendment, before the main run. The main and Sonnet stages refuse a partial corpus.
- **Tasks.** 32 evaluation tasks (`tasks/`), phrased the way a teammate asks: the interface to build, no hint of the lesson.
  - **M** (14), memory-only: the rule is stated only in earlier sessions, reviews or chat. No line of main matches the lesson's evidence patterns in `lessons.yaml`.
  - **D** (4), discoverable: main's code already follows the convention.
  - **S-u** (4), stale and unrecorded: memory holds an old rule. Main shows the new one (a deprecation, the changelog and the code), and no session recorded the change.
  - **S-s** (4), superseded: memory holds both the old rule and the later session that changed it; main shows the new one.
  - **X** (2), cross-repo: another repo's memory holds the opposite convention; this repo's code shows its own.
  - **C** (4), control: memory is irrelevant.
- **Grading.** Hidden tests only, no LLM judge.
  - Every test name carries a kind:
    - `func`: does the feature work;
    - `lesson`: does it follow the lesson;
    - `diag`: a diagnostic, such as "followed the old rule". Never scored.
  - An episode passes when it ends with `finish` and every `func` and `lesson` test passes.
  - The candidate tree is main plus only the task's editable paths from the agent's workspace. It never includes `conftest.py`, `pytest.ini`, `sitecustomize.py`, `package.json` or similar.
  - Hidden tests run in a separate sandboxed process with no network. That process can write only in its grading directory, and it cannot read file contents anywhere under the home directory (including the benchmark, its git history and other workspaces) or in the shared temp directories (`/private/tmp`, `/private/var/tmp`, `/private/var/folders`). The exceptions are its own directory and the project's Python environment.
  - The JUnit test set must equal the hidden file's test set exactly.
  - Every run also includes tests that must fail: one per assertion helper (TypeScript), and a plain `assert` plus `pytest.raises` (Python). If any of them passes, something patched the assertions or the runner; the episode is marked tampered, scores 0, and is hand-checked.
  - The runner's summary must agree with the JUnit report, or the run is marked `junit_mismatch` and scores 0. The output keeps its head and its tail.
    - pytest: exactly one line in the whole output must fully match pytest's summary format (counts, then "in N s"), and it must be the last line.
    - node: the output must end with node's TAP summary block (tests, suites, pass, fail, cancelled, skipped, todo, duration_ms).
  - A report that can't be read or parsed is `no_junit` and scores 0.
  - Candidate code is flagged and hand-checked when an added line matches the static patterns in `smb/grade.py`. `SUSPICIOUS` covers the test machinery: the report, argv, assertion modules and dunder tricks. `TRIPWIRE` covers the words test, junit, argv, summary, weakref, finalize, `__del__`, threading, `_thread`, dup2, listdir, scandir, glob, iterdir, `walk(`, readdir and the parent directory. A determined candidate could still forge a run; that residual risk is stated in section 7.
  - Graders run with `TZ=America/Los_Angeles`. A grading run that times out is retried once with twice the time.

## 2. Conditions

Same model, system prompt, task prompt, tools and budgets in every condition; only memory differs. Memory is appended to the task prompt in a `<team-memory>` block whose wording is fixed in `smb/memory/provider.py`.

| id | condition | what the agent gets |
|---|---|---|
| a | none | no memory |
| b | raw | this repo's session transcripts, newest first, whole sessions only, plus all chat messages, up to **40,000 tokens**. Counted once at corpus freeze by the Messages API `count_tokens` endpoint for `claude-haiku-5-5` (`raw_blocks.json`). Tool inputs are clipped to 2,000 characters and tool results to 800; task, review and agent text stay verbatim. With the per-request guard (section 3), every request stays under the 100,000-token long-prompt price tier. |
| c | retrieved | chunks from an org-wide index (all four repos and chat): hybrid BM25 and bge-small-en-v1.5, fused by reciprocal rank, up to 7,000 characters. Each chunk shows date, repo, branch or channel, kind and author. The query is the submitted prompt + the previous assistant turn + `repo: <repo> branch: <branch>`, which is the payload a memory hook receives when a prompt is submitted. At the start of a session the previous assistant turn is empty. Injected once, with the prompt. |
| d | distilled | notes distilled once per history session by `claude-haiku-5-5` with the fixed prompt in `smb/memory/distill.py` (at most 8 per session, dated). The index holds those notes plus the team chat messages verbatim, because chat is already short and this keeps the chat-only lessons reachable in every memory condition. Retrieved by the same method and query, up to 3,500 characters. |
| f | pull | nothing injected; a `search_memory(query)` tool over the same index as c (7,000 characters per call). The system prompt gains one sentence naming the tool. |
| g | oracle | the exact current lesson notes for the task (`lessons.yaml`): the ceiling, and a check that the task is solvable |

## 3. Agent and budgets

- **Loop.** A minimal loop on the Messages API (`smb/agent.py`).
- **Tools.** `list_dir`, `read_file`, `search_code`, `write_file`, `replace_in_file`, `run_tests` and `finish`, plus `search_memory` in f. No shell.
  - `run_tests` runs the visible suite or one path, sandboxed like the graders, with `TZ=America/Los_Angeles`.
  - Agent mistakes go back to the agent as error results. That covers unknown tools, bad arguments, bad or non-regular paths, bad regular expressions, a search running longer than 10 seconds, and files or directories the agent's own code made unreadable (which are skipped). A failure of the harness itself, such as the retriever or the test sandbox failing to start, ends the episode as a harness error.
  - The file tools run on the host, inside the workspace only, and never follow or list symbolic links, even ones that point inside the workspace.
  - Every open walks directory file descriptors with `O_NOFOLLOW`, so a path swapped for a link between two calls is not followed either.
  - Files over 1 MB are refused by `read_file` and skipped by searches and by the grader's snapshot. Entries more than 64 directories deep are skipped.
  - The snapshot takes only the task's editable files. If they exceed 20 MB in total, the episode ends as a harness error rather than being graded on part of its files.
  - `search_code` runs its regex in a sandboxed child process that receives the file contents, with a 10-second deadline.
  - After each run, a process is killed (best effort) if it is sandboxed, started after the run's directory was created, and still has its working directory or an open file there. This catches processes that runs left behind outside their process group. Unsandboxed processes are never touched. Sandboxed code can signal only processes in its own sandbox.
- **Per episode.**
  - At most 30 model calls, `max_tokens` 8,000, prompt caching on, and the model's default effort.
  - A 10-minute wall clock, checked between calls; each call times out after 180 seconds.
  - A request whose estimated prompt exceeds 95,000 tokens is not sent, and the episode ends `context_limit`.
  - A reply cut off by `max_tokens` has none of its tool calls run.
  - Transient API errors are retried up to 3 attempts. Each attempt reserves its own worst case, and an attempt that may have been billed (timeout, dropped connection, server error) is booked at that worst case.
- **Main run.** `claude-haiku-5-5`, all 32 tasks × 6 conditions × **3 epochs** (576 episodes). If the pilot projects this above the main stage cap ($12), the main run uses 2 epochs instead. That choice is recorded as a dated amendment before the main run starts.
- **Cross-check.** `claude-sonnet-5-5` on the 8 S tasks, 1 epoch, run as (a, c) pairs task by task until the $3 cap, then d if money remains. Incomplete pairs are reported and excluded from tests.
- **History and distillation** use `claude-haiku-5-5`.

## 4. Outcomes and hypotheses

Unit: one episode (task × condition × epoch). Outcome: pass (1) or fail (0).
- Episodes that end in `cap` or a harness `error` are excluded from both sides of a pair and reported.
- `context_limit`, `call_limit`, `wall_clock`, `no_finish` and `refusal` count as fails, whatever the workspace would have graded. The would-be grade is recorded.

Tests: exact McNemar on outcomes paired by (task, epoch), with Holm within each family at α = 0.05. Robustness: the paired difference with a 95% task-cluster bootstrap interval (10,000 resamples, seed 0).

**Family A: benefit, on M tasks (Holm over 4)**
- A1: c passes more often than a (one-sided).
- A2: d vs c (two-sided).
- A3: b vs c (two-sided).
- A4: f vs c (two-sided).

**Family B: harm, co-primary, on S tasks (S-u ∪ S-s; Holm over 4)**
- B1–B4: each of b, c, d and f passes less often than a (one-sided).
- Reported with each condition's failure rate on S tasks (Wilson 95%) and the failure breakdown below.

**Failure breakdown, from the labels and the test kinds**
- **Any task.** An episode that wasn't graded (the module didn't import, tampered, grader timeout) is reported as *not graded* with its status. One that didn't end with `finish` is reported as *unfinished* with its stop reason. The categories below apply to graded, finished failures.
- **M and D tasks.** Only lessons with a memory source are counted.
  - *not retrieved*: some needed lesson is in no recalled item;
  - *retrieved, not applied*: every needed lesson was recalled, but a `lesson` test failed;
  - *other*.
- **X tasks**, whose own rule lives only in the code. *followed the other repo's rule* (a `diag` test passed); *other*.
- **C tasks.** *other*.
- **What counts as recalled.**
  - b: the lesson's span is inside the injected block.
  - c and f: a recalled chunk carries a span (section 5).
  - d: a recalled note's frozen hand label, or a recalled chat message's span label.
- **S-s tasks.** *followed the old rule* (a `diag` test passed); *current rule recalled, not applied*; *other*.
- **S-u tasks**, where memory never holds the current rule. *followed the old rule*; *old rule recalled, not followed, other failure*; *other*.

**Write-up rule.** If c and g both pass at least 90% of M episodes (accuracy saturates), the write-up leads with Family B (harm) and cost. Otherwise Families A and B are co-headlines.

**Secondary (descriptive, no correction)**
- pass rates by family × condition (Wilson);
- tokens, dollars, calls and wall clock per episode and per solved task;
  - D tasks against a (token savings);
  - b's tokens and dollars per solved task;
- read and search calls before the first edit;
- X contamination rate and C distraction (pass rate and tokens against a);
- retrieval precision and lesson recall:
  - precision: the share of recalled chunks whose source is a labelled source of a needed lesson;
  - recall: the share of needed lessons that were recalled;
  - both for the org-wide index used by c and f, and offline for a repo-filtered index;
- f: the share of episodes that searched at all, and searches per episode;
- S-s: old rule against new rule followed;
- the Sonnet cross-check.

## 5. Labels

- Which session, review comment or chat message carries which lesson is fixed in `history/*.yaml` before any run.
- For each source, `lessons.yaml` `spans` gives the exact sentence or sentences that state the rule. Each is checked to be a substring of a text tagged with that lesson.
- A chunk carries a lesson when it contains at least 60 consecutive characters of one of the lesson's spans, compared at every offset after collapsing whitespace, or the whole span if it is shorter.
- Model-distilled notes paraphrase. After distillation and before freeze, every note is labelled by hand with the lessons it states, using the definitions in `lessons.yaml`. The labels are frozen in `notes_labels.json`, and freeze refuses unreviewed labels. The pattern labels in `lessons.yaml` are reported next to them as an automated cross-check.

## 6. Gates and stop rules

**G1 ($0, before any model call)**
- Every task's solution matrix holds and is identical over 5 repeats under concurrent graders:
  - the oracle scores 1 with no diagnostic firing;
  - the no-op scores 0;
  - the visible-only solution scores 0 with a lesson test failing;
  - the stale and other-repo solutions score 0 with their diagnostic firing.
- Every solution passes the visible suite under `TZ=UTC`.
- Main and every history start state pass their visible suites under `TZ=UTC`.
- History checks behave as listed in `scripts/validate.py`.
- Memory-only lessons have no evidence-pattern match in main.
- No new oracle line of 25+ characters, generic or not, and no hidden-test string literal of 12+ characters appears in any memory text we wrote. Imports, comments and anything already present in main are skipped.
- The stub end-to-end run is clean: the no-memory stub scores 0 on M and D, and the oracle stub passes every task.

**G2 (pilot)**
- What runs: billing's history, then billing's 8 tasks × 6 conditions × 1 epoch, plus a and g on the other 10 M tasks × 1 epoch.
- Gates:
  - over all 14 M tasks, g ≥ 70% and a ≤ 30%;
  - on billing's C and D tasks together, a passes at least 1 of 2.
- If a gate fails, the tasks are redesigned before any further spend, and the redesign is recorded as an amendment.
- M tasks that a solves in the pilot are named in the write-up as inferable without memory.

**G3 (spend)**
- Every model request reserves its worst case before it is sent: 1 token per character of input at the higher of the input and cache-write prices, plus the full `max_tokens` of output.
- The SDK makes no retries of its own.
- Stage caps:
  - pilot (billing history, its distillation and the pilot episodes): $1.50;
  - history (the other 19 sessions and their distillation): $1.00;
  - main: $12;
  - Sonnet: $3;
  - total: $17.50 of a $20 budget.
- Each stage's meter starts from what that stage has already booked in the spend ledgers. A lock file allows one process per stage, so a resumed stage stays within its cap. A freeze holds the pilot and history locks, so no distillation writes notes while they are checked and hashed.
- A command runs only in its own stages (history and distillation: pilot for billing, history for the rest; eval: pilot, main or Sonnet).
- Distillation goes through the same reservation and retry rules, and saves its notes after every session.
- A stage stops at its cap. Episodes stopped by the cap are reported, not scored.

**G4 (hand checks)**
- Checked by hand:
  - every a pass on an M task;
  - every S task where a and c disagree;
  - every episode flagged by the grader's tamper patterns;
  - every grading timeout, and every run marked `junit_mismatch`, `no_junit` or `tampered`;
  - a random 10% of the rest (seed 0), drawn from scored episodes not already on these lists.
- A grader or task defect found this way is fixed, and every condition is re-graded the same way, with a log in the run directory. The task is fixed, or excluded with the reason.

**Leakage**
- Answer strings are:
  - oracle lines of 25+ characters that use an identifier or a string literal main doesn't have (imports and comments skipped);
  - hidden-test string literals of 12+ characters;
  - in both cases, only strings not already present anywhere in main.
- For the agents' transcripts and notes, oracle lines whose names (3+ characters) and string literals (3+ characters) all already appear in main are left out on purpose. A history agent that writes such a line is producing memory of a lesson, not copying an answer. Texts we wrote ourselves are checked against every new oracle line (G1).
- At freeze, no answer string may appear in any chunk, note or raw block.
- A string that is a false positive is allowed only through a reviewed list recorded as an amendment; the list is part of the corpus hash.

## 7. Known limits

- One draw of history sessions.
- One fictional organization.
- Small task counts: M 14, S 8.
- Small synthetic repos.
- Haiku is not the model most production agents run, and the Sonnet cross-check is small.
- Graded code shares a process with the hidden tests, so a determined candidate could tamper with the run. The grader allowlists editable paths, checks the exact JUnit set and flags suspicious references; flagged passes are hand-checked.

## Amendments

### Amendment 1 — 2026-10-23, after the pilot, before the other repos' history stage and the main run

The pilot (PILOT.md) passed G2 and spent $0.27. It projects the 3-epoch main run at about $2.3.

1. **Epochs.** The main run uses **5 epochs** (32 tasks × 6 conditions × 5 = 960 episodes) instead of 3.
   - Reason: cost and power. 3 epochs would use about a fifth of the $12 main cap, and the harm family has few pairs at 3 epochs (24 per condition on the 8 S tasks); 5 epochs give 40.
   - This was decided before any main-run episode. The pilot data seen at that point: billing's 8 tasks at 1 epoch, and a and g on the other 10 M tasks.
   - Pilot episodes are not pooled with the main run. Nothing else in section 3 changes.
2. **Added descriptive analyses.** They are reported next to the registered ones, with no tests and no Holm correction.
   - **Retrieval misses**, per memory condition (b, c, d, f), on tasks whose lessons memory could supply.
     - A *strict* miss: a needed lesson's rule sentence (span label) is not in the recalled memory.
     - A *clear* miss: none of the lesson's patterns is there either.
     - For each clear miss in b, c or d, we report whether f, on the same task and epoch, recalled the lesson (span or pattern) and passed.
   - **Dollars per solved task**, per condition, for all tasks and for M, S and X separately.
   - **Change visibility on S tasks.**
     - Each S task's `task.yaml` now pins `change_evidence`: the changelog line, and the code or deprecation line in main, that show the change. `validate.py` checks that each string is in main. No task, test or grading changes.
     - An episode *saw* the change when one of those strings appears in what `list_dir`, `read_file`, `search_code` or `run_tests` returned to the agent. `search_memory` results don't count.
     - Reported per condition and task: episodes that saw the change, pass rates when it was seen and when it wasn't, and old-rule follows (a `diag` test passing). This explains a harm result or its absence; it is not a test.
3. **Note labels (section 5), as applied.** A note is labelled with a lesson only if it states that lesson's rule. Mentions, hints and process notes stay unlabelled. The pilot's 50 billing notes were labelled this way, and the other repos' notes will be too.
