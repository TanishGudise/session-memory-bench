# Main run results, 2026-10-23

`claude-haiku-5-5`, 32 tasks × 6 conditions × 5 epochs = 960 episodes (Amendment 1). Manifest `38c856a4…` (FROZEN at run start), corpus `run1` `9b4cdf34…` (Amendment 2).

- All 960 episodes finished. 959 were graded; 1 is a collection error, scored 0 (`ingest-01__c__e1`, where the agent finished without code to ask a question).
- No episode was excluded, marked tampered, timed out or booked at worst case.
- Analysis: `scripts/analyze.py runs/eval/main --corpus runs/history/run1`.
- With notify-05 excluded under G4 (Amendment 3): the same command with `--exclude-tasks notify-05 --out runs/eval/main/g4_excl_notify-05`.

## Pass rates

notify-05 is excluded under G4 (a task defect, Amendment 3). The numbers as run, with it included, are in brackets where they differ.

| Condition | M (memory needed) | D | S-u | S-s | X | C |
|---|---|---|---|---|---|---|
| a none | 10/70 (14%) | 20/20 | 15/15 [16/20] | 20/20 | 10/10 | 20/20 |
| b raw transcripts | 69/70 (99%) | 20/20 | 15/15 [19/20] | 20/20 | 10/10 | 20/20 |
| c retrieved (hook-shaped query) | 29/70 (41%) | 19/20 | 15/15 [18/20] | 20/20 | 10/10 | 20/20 |
| d distilled notes | 55/70 (79%) | 20/20 | 15/15 [20/20] | 20/20 | 10/10 | 20/20 |
| f search tool | 44/70 (63%) | 20/20 | 15/15 [19/20] | 20/20 | 10/10 | 20/20 |
| g oracle | 68/70 (97%) | 20/20 | 15/15 [15/20] | 20/20 | 10/10 | 20/20 |

Wilson 95% intervals on M: a [0.08, 0.24], b [0.92, 1.00], c [0.31, 0.53], d [0.68, 0.87], f [0.51, 0.73], g [0.90, 0.99]. Not saturated (c on M is 41%).

## Family A, benefit on M (exact McNemar, Holm over 4; task-cluster bootstrap 95% CI)

notify-05 is not an M task, so these are the same with or without it.

| Test | Discordant (x only / y only) of 70 pairs | p (Holm) | Difference [95% CI] |
|---|---|---|---|
| A1 c > a | 20 / 1 | <0.0001 | +0.27 [+0.04, +0.50] |
| A2 d vs c | 28 / 2 | <0.0001 | +0.37 [+0.11, +0.63] |
| A3 b vs c | 41 / 1 | <0.0001 | +0.57 [+0.30, +0.81] |
| A4 f vs c | 20 / 5 | 0.0041 | +0.21 [−0.04, +0.49] |

A4's episode-level test passes, but its task-clustered interval includes 0.

## Family B, harm on S (exact McNemar, one-sided "memory worse than none", Holm over 4)

| Test | Without notify-05: discordant (memory only fails / none only fails) of 35 | As run: of 40 | p (Holm), both |
|---|---|---|---|
| B1 b < a | 0 / 0 | 0 / 3 | 1.00 |
| B2 c < a | 0 / 0 | 1 / 3 | 1.00 |
| B3 d < a | 0 / 0 | 0 / 4 | 1.00 |
| B4 f < a | 0 / 0 | 0 / 3 | 1.00 |

S failure rates:
- **Without notify-05:** 0/35 in every condition (Wilson upper bound 0.10).
- **As run:** a 4/40 [0.04, 0.23], b 1/40 [0.00, 0.13], c 2/40 [0.01, 0.17], d 0/40 [0.00, 0.09], f 1/40 [0.00, 0.13], g 5/40 [0.06, 0.26].

No episode in any condition followed the old rule: every `diag` test failed. No harm was detected. That is a weak bound from the registered test alone: at Holm's first step (one-sided α = 0.0125), a condition needs at least 7 one-way discordant pairs of 40, about 18 points, to register harm. The raw counts are the tighter evidence: outside notify-05, no memory-condition episode failed an S task.

**Change visibility on S tasks (Amendment 1).**
- In 238 of the 240 S episodes, what the code tools returned to the agent contained the change. In 237 that was the code or deprecation line, always through `read_file`; in 86 it was the changelog.
- That line sits in existing code that the new code calls or mirrors; no agent edited it.
- No episode followed the old rule. That includes the memory-condition episodes whose memory held it (span or pattern): b 40, c 30, d 40 and f 19 of 40.
- This is consistent with the agents taking the current rule from the code over memory. But with only 2 episodes that didn't see the change, this run can't show that seeing it is what prevented harm.
- Every S task shows the change in the code (PREREGISTRATION section 1), so harm from a change the code doesn't show is not tested.

**notify-05, excluded under G4 (Amendment 3).**
- It surfaced through G4's "S tasks where a and c disagree" list (4 pairs, all notify-05).
- Its functional test (`test_func_sends_to_users_with_email`) passes a user with no email address and expects that user to be skipped. `mailer.dispatch()` raises for such a user, and the prompt doesn't say to skip them. That requirement is unrelated to the lesson under test.
- All 30 notify-05 episodes passed both lesson tests (opt-out skip, List-Unsubscribe header), and none followed the old rule. All 13 S failures as run are this one test.

## Retrieval misses (Amendment 1)

- A *strict* miss: a needed memory lesson was not recalled by section 4's rule (span labels; hand labels for d's notes).
- A *clear* miss: not even one of the lesson's patterns was in the recalled memory.
- These are on M, D and S-s tasks and are unaffected by notify-05.

| Condition | Episodes with memory lessons | Strict misses | Clear misses | Clear misses solved anyway |
|---|---|---|---|---|
| b raw | 110 | 0 | 0 | — |
| c retrieved | 110 | 85 | 35 | 15 |
| d distilled | 110 | 15 | 5 | 0 |
| f search | 110 | 59 | 29 | 10 |

Lesson recall by span label (hand label for d's notes): b 1.00, d 0.88, f 0.51, c 0.25. Chunk precision (share of recalled chunks from a source of a needed lesson): c 0.50, f 0.59.

**c's clear misses, and whether search recovered them (the billing-04 pattern).** On the 35 c episodes with a clear miss, f on the same task and epoch recalled the missing lesson and passed in 24.

| Lesson c missed | Source | Clear misses | f recalled it and passed |
|---|---|---|---|
| ingest.dmy-dates | session ingest-H6 | 10 | 4 |
| billing.settlement-tz-flake | session billing-H3 | 5 | 5 |
| billing.refund-second-approver | chat | 5 | 5 |
| ingest.kestrel-berlin-time | session ingest-H1 | 5 | 5 |
| ingest.null-qty-quarantine | session ingest-H4 | 5 | 4 |
| inventory.withtx | session inventory-H5 | 5 | 1 |

**Exploratory, after the run:** do the clear misses track how lexical the lesson is in the prompt? `scripts/explore_retrieval_misses.py runs/eval/main runs/history/run1` gives:
- Word overlap between the prompt and the rule spans averages 0.13 for the 7 missed task-lesson pairs and 0.18 for the 17 recalled ones, and the groups overlap widely: two missed pairs sit at 0.25, two recalled ones at 0.0.
- The best rule-carrying chunk's rank medians are 21 (BM25) and 27 (dense) for missed pairs, and 18 and 18 for recalled ones.
- Neither measure separates the misses. Of the 35 clear misses, c still passed 15. f fixed 14 of the 20 c failures.

f searched in 94% of episodes (0.98 searches per episode). Its own clear misses are spread across 10 lessons; the largest are dmy-dates 6, then withtx, formal-german (chat), redact-pii and rno-returns-only (chat) at 4 each.

## Dollars per solved task (Amendment 1), as run

Priced from the usage of answered calls. No call was booked at its worst case, so these equal booked spend.

| Condition | All tasks | M | S | X |
|---|---|---|---|---|
| a none | $0.0038 | $0.0168 | $0.0023 | $0.0027 |
| b raw | $0.0076 | $0.0083 | $0.0072 | $0.0073 |
| c retrieved | $0.0037 | $0.0075 | $0.0026 | $0.0028 |
| d distilled | $0.0029 | $0.0038 | $0.0023 | $0.0027 |
| f search | $0.0037 | $0.0056 | $0.0027 | $0.0034 |
| g oracle | $0.0023 | $0.0028 | $0.0021 | $0.0021 |

Raw transcripts solve the most M tasks but cost about 2.2× as much per solve as distilled notes on M (2.6× over all tasks). Each repo's raw block is 29k–35k tokens. The largest single request was 47,239 tokens (pilot 45,947), so none reached the 100k price tier.

## Spend

| Stage | Requests | $ |
|---|---|---|
| pilot (billing history, distillation, 68 episodes) | 505 | 0.2695 |
| history (19 sessions + 1 discarded draw) and distillation | 181 | 0.0966 |
| main (960 episodes) | 5,528 | 3.2754 |
| total | 6,214 | **3.6415** |

Plus one request that never returned usage (the hung history call, Amendment 1 item 4), which is not booked. Two history requests were booked at worst case ($0.0149 together).

## Hand checks (G4)

- **Flagged by the tamper patterns:** 3, all benign: a `User(**{**user.__dict__, ...})` copy, a comment mentioning `Array.prototype.sort`, and an empty TS test file with a comment.
- **a passes on M:** 10, all `billing-02` and `ingest-02` (every epoch), the same two the pilot found inferable without memory. Checked and genuine.
- **S pairs where a and c disagree:** 4, all notify-05. It was found to be a task defect and excluded (above).
- **Random 10%:** 93 episodes.
  - 78 passed, all graded, none following an old rule.
  - 15 failed: 13 on a lesson test whose lesson the agent didn't apply, and 2 on notify-05's functional test.
- **Tampered, JUnit mismatch, grader timeouts:** none.

The other registered descriptives (failure breakdown, tokens, calls and wall clock, reads before the first edit, X and C results, offline recall and precision) are in `analysis.json`.

## Deviation

The last 149 episodes finished on battery: the result files written after 18:34:32, when 811 of 960 were done. That breaks Amendment 1 item 4's AC rule.
- The lid stayed open; the battery read 95% at 18:34 (`pmset -g batt`).
- The power log shows no sleep or wake event in that window.
- `caffeinate -s` has no effect on battery; sleep was held off by another idle-sleep assertion and the display.
- No call was abandoned or booked at worst case.

## Data

`runs/` (results, transcripts, ledgers, corpus) is not in git. The private repo will ship it as a separate data release.

## Limits

- Synthetic repos, one fictional organization and one draw of history sessions.
- Haiku only so far; the Sonnet cross-check has not run.
- Small task counts: 14 M, and 8 S, 7 after the G4 exclusion.
- The harm family rests on few failures. Outside notify-05, every S episode passed in every condition.
- The S tasks always show the change in the code. A stale rule that the code doesn't show is not tested here.
