# Main run results, 2026-10-23

`claude-haiku-5-5`, 32 tasks × 6 conditions × 5 epochs = 960 episodes (Amendment 1). Manifest `38c856a4…` (FROZEN at run start), corpus `run1` `9b4cdf34…` (Amendment 2). All 960 episodes finished; 959 graded and 1 collection error (scores 0). No episode was excluded, flagged as tampered, timed out or booked at worst case. Analysis: `scripts/analyze.py runs/eval/main --corpus runs/history/run1`.

## Pass rates

| Condition | M (memory needed) | D | S-u | S-s | X | C |
|---|---|---|---|---|---|---|
| a none | 10/70 (14%) | 20/20 | 16/20 | 20/20 | 10/10 | 20/20 |
| b raw transcripts | 69/70 (99%) | 20/20 | 19/20 | 20/20 | 10/10 | 20/20 |
| c retrieved (hook-shaped query) | 29/70 (41%) | 19/20 | 18/20 | 20/20 | 10/10 | 20/20 |
| d distilled notes | 55/70 (79%) | 20/20 | 20/20 | 20/20 | 10/10 | 20/20 |
| f search tool | 44/70 (63%) | 20/20 | 19/20 | 20/20 | 10/10 | 20/20 |
| g oracle | 68/70 (97%) | 20/20 | 15/20 | 20/20 | 10/10 | 20/20 |

Wilson 95% intervals on M: a [0.08, 0.24], b [0.92, 1.00], c [0.31, 0.53], d [0.68, 0.87], f [0.51, 0.73], g [0.90, 0.99]. Not saturated (c on M is 41%).

## Family A, benefit on M (exact McNemar, Holm over 4; task-cluster bootstrap 95% CI)

| Test | Discordant (x only / y only) of 70 pairs | p (Holm) | Difference [95% CI] |
|---|---|---|---|
| A1 c > a | 20 / 1 | <0.0001 | +0.27 [+0.04, +0.50] |
| A2 d vs c | 28 / 2 | <0.0001 | +0.37 [+0.11, +0.63] |
| A3 b vs c | 41 / 1 | <0.0001 | +0.57 [+0.30, +0.81] |
| A4 f vs c | 20 / 5 | 0.0041 | +0.21 [−0.04, +0.49] |

A4's episode-level test passes, but its task-clustered interval includes 0.

## Family B, harm on S (exact McNemar, one-sided "memory worse than none", Holm over 4)

| Test | Discordant (x only / y only) of 40 pairs | p (Holm) |
|---|---|---|
| B1 b < a | 3 / 0 | 1.00 |
| B2 c < a | 3 / 1 | 1.00 |
| B3 d < a | 4 / 0 | 1.00 |
| B4 f < a | 3 / 0 | 1.00 |

No harm was detected: no memory condition failed an S task that no-memory passed more often than the reverse. No episode in any condition followed the old rule (every `diag` test failed).

**Why no harm (Amendment 1, change visibility).** In 238 of the 240 S episodes, what the code tools returned to the agent contained the change. In 237 that was the code or deprecation line, and in 86 the changelog. The agents read the code they were about to change, saw the current rule there, and followed it over memory. Harm from stale memory would need a change that the code doesn't show; this benchmark's S tasks always show it (PREREGISTRATION section 1, S-u and S-s definitions).

**notify-05 (found after the run, not rescored).** All S failures in every condition come from one functional test of notify-05 (`test_func_sends_to_users_with_email`). It passes a user with no email address and expects them to be skipped. `mailer.dispatch()` raises for such a user, and the prompt doesn't say to skip them. All 30 notify-05 episodes passed both lesson tests (opt-out skip, List-Unsubscribe header) and none followed the old rule. Excluding notify-05, every condition passes 35/35 S episodes. The preregistered tests above include it.

## Retrieval misses (Amendment 1)

A *strict* miss: a needed memory lesson was not recalled by section 4's rule. A *clear* miss: not even one of its patterns was in the recalled memory.

| Condition | Episodes with memory lessons | Strict misses | Clear misses | Clear misses solved anyway |
|---|---|---|---|---|
| b raw | 110 | 0 | 0 | — |
| c retrieved | 110 | 85 | 35 | 15 |
| d distilled | 110 | 15 | 5 | 0 |
| f search | 110 | 59 | 29 | 10 |

Lesson recall by span label: b 1.00, d 0.88, f 0.51, c 0.25. Chunk precision (share of recalled chunks from a source of a needed lesson): c 0.50, f 0.59.

**c's clear misses, and whether search recovered them (the billing-04 pattern).** On the 35 c episodes with a clear miss, f on the same task and epoch recalled the missing lesson and passed in 24.

| Lesson c missed | Source | Clear misses | f recalled it and passed |
|---|---|---|---|
| ingest.dmy-dates | session ingest-H6 | 10 | 4 |
| billing.settlement-tz-flake | session billing-H3 | 5 | 5 |
| billing.refund-second-approver | chat | 5 | 5 |
| ingest.kestrel-berlin-time | session ingest-H1 | 5 | 5 |
| ingest.null-qty-quarantine | session ingest-H4 | 5 | 4 |
| inventory.withtx | session inventory-H5 | 5 | 1 |

f searched in 94% of episodes (0.98 searches per episode). Its own clear misses are spread across 10 lessons; the largest are dmy-dates 6, then withtx, formal-german (chat), redact-pii and rno-returns-only (chat) at 4 each.

## Dollars per solved task (Amendment 1)

Priced from the usage of answered calls. No call was booked at its worst case, so these equal booked spend.

| Condition | All tasks | M | S | X |
|---|---|---|---|---|
| a none | $0.0038 | $0.0168 | $0.0023 | $0.0027 |
| b raw | $0.0076 | $0.0083 | $0.0072 | $0.0073 |
| c retrieved | $0.0037 | $0.0075 | $0.0026 | $0.0028 |
| d distilled | $0.0029 | $0.0038 | $0.0023 | $0.0027 |
| f search | $0.0037 | $0.0056 | $0.0027 | $0.0034 |
| g oracle | $0.0023 | $0.0028 | $0.0021 | $0.0021 |

Raw transcripts solve the most M tasks but cost about twice as much per solve as distilled notes. Each repo's raw block is 29k–35k tokens, so no request reached the 100k price tier.

## Spend

| Stage | Requests | $ |
|---|---|---|
| pilot (billing history, distillation, 68 episodes) | 505 | 0.2694 |
| history (19 sessions + 1 discarded draw) and distillation | 183 | 0.0966 |
| main (960 episodes) | 5,528 | 3.2754 |
| total | 6,216 | **3.6415** |

Plus one request that never returned usage (the hung history call, Amendment 1 item 4), which is not booked. Two history requests were booked at worst case ($0.0149 together).

## Hand checks (G4)

- **Flagged:** 3, all benign: a `User(**{**user.__dict__, ...})` copy, a comment mentioning `Array.prototype.sort`, and an empty TS test file with a comment.
- **a passes on M:** 10, all `billing-02` and `ingest-02` (every epoch), the same two the pilot found inferable without memory. Checked and genuine.
- **S tasks where a and c disagree:** 4, all notify-05 (see above).
- **Random 10%:** 93 episodes. 78 passed, all graded, none following an old rule. 15 failed, each on a lesson test whose lesson the agent didn't apply, or on notify-05's functional test.
- **Tampered, JUnit mismatch, grader timeouts:** none.

## Deviation

The last 149 episodes (after 811 of 960, from 18:34) ran on battery, against Amendment 1 item 4's AC rule. The lid stayed open, battery started at 95%, and the power log shows no sleep in that window. No call was abandoned or booked at worst case.

## Limits

Synthetic repos, one fictional organization and one draw of history sessions. Haiku only so far; the Sonnet cross-check has not run. Small task counts (14 M, 8 S). The S tasks always show the change in the code; a stale rule that the code does not show is not tested here.
