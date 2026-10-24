# Extension results: invisible changes (ext/ADDENDUM.md), 2026-10-23

`claude-haiku-5-5`, 5 S-i tasks × 6 conditions × 10 epochs = 300 episodes. Manifest `31957386…` (FROZEN at run start), corpus `ext1` `cc7dcc25…`: run1's sessions and notes byte-identical, plus the five chat messages, 510 chunks. All 300 episodes finished and were graded. None was excluded, timed out or booked at worst case. Spend $0.9676 (1,727 requests). Analysis: `scripts/analyze_ext.py runs/eval/ext`.

In each task, the rule changed only in a later chat message, and the code the agent reads shows neither rule.

## Outcomes per condition (50 episodes each; Wilson 95% intervals)

| Condition | New rule (pass) | Old rule followed | Other |
|---|---|---|---|
| a none | 0 [0.00, 0.07] | 0 [0.00, 0.07] | 50 |
| b raw transcripts | 50 [0.93, 1.00] | 0 [0.00, 0.07] | 0 |
| c retrieved (hook-shaped query) | 10 [0.11, 0.33] | 20 [0.28, 0.54] | 20 |
| d distilled notes | 39 [0.65, 0.87] | 10 [0.11, 0.33] | 1 |
| f search tool | 38 [0.63, 0.86] | 0 [0.00, 0.07] | 12 |
| g oracle | 50 [0.93, 1.00] | 0 [0.00, 0.07] | 0 |

## Primary: harm, i.e. following the old rule more often than no memory (exact McNemar, one-sided, Holm over 4)

| Test | Memory only / no memory only, of 50 pairs | p (Holm) |
|---|---|---|
| b < a | 0 / 0 | 1.00 |
| c < a | 20 / 0 | <0.0001 |
| d < a | 10 / 0 | 0.003 |
| f < a | 0 / 0 | 1.00 |

Retrieved snippets and distilled notes caused measurable harm; raw transcripts and the search tool did not.

## What the recalled memory held (span labels; hand labels for d's notes)

| Recalled memory held | Episodes (b, c, d, f) | New rule | Old rule | Other |
|---|---|---|---|---|
| both the old and the new decision | 139 | 137 | 0 | 2 |
| only the old decision | 30 | 0 | 30 | 0 |
| neither | 31 | 0 | 0 | 31 |
| only the new decision | 0 | — | — | — |

- Every old-rule outcome came from memory that held only the old decision.
- When both decisions were in context, the agent followed the newer one in 137 of 139 episodes. The other 2 failed for other reasons.
- So the harm is a retrieval problem: the older decision was surfaced without the one that replaced it.

**By task:**
- Retrieved snippets surfaced only the old rule on Bramblecote case size (10 of 10) and quiet hours (10 of 10), and missed both on the refund threshold and allocation.
- Distilled notes surfaced only the old returns-only warehouse on allocation (10 of 10).
- Raw transcripts put the team chat first, newest first, and held both decisions in every episode.
- The search tool searched in 96% of episodes. It recalled both decisions or neither, never the old one alone.

| Task | a | b | c | d | f | g |
|---|---|---|---|---|---|---|
| billing-i1 (reminder floor $1 → $5) | 0/0 | 10/0 | 10/0 | 10/0 | 9/0 | 10/0 |
| billing-i2 (refund approver over $500 → $250) | 0/0 | 10/0 | 0/0 | 9/0 | 9/0 | 10/0 |
| inventory-i1 (Bramblecote cases 6 → 12) | 0/0 | 10/0 | 0/10 | 10/0 | 10/0 | 10/0 |
| inventory-i2 (returns-only RNO → EWR) | 0/0 | 10/0 | 0/0 | 0/10 | 0/0 | 10/0 |
| notify-i1 (quiet hours 20-09 → 21-10) | 0/0 | 10/0 | 0/10 | 10/0 | 10/0 | 10/0 |

(cells: new rule / old rule, of 10)

## Cost

$ per solved task (answered calls): oracle $0.0029, distilled $0.0039, search $0.0046, raw $0.0047, retrieved $0.0140. No-memory runs solved none. The ledger holds 1,727 requests, $0.9676, with no worst-case bookings.

## Hand checks (ADDENDUM section 6)

- **a passes:** none.
- **Old-rule outcomes in b, c, d, f:** 30, all checked. Each wrote the old value from memory (cases of 6; quiet hours 20:00-09:00; "RNO is returns-only"), and each one's recalled memory held only the old decision.
- **Flagged:** 3, all benign comments about `Array.prototype.sort` being stable.
- **Random 10%:** 26, all consistent. Every pass applied the new rule. Every "other" recalled neither rule, so it applied no rule. None followed the old rule.

## Limits

- Five tasks, each change carried by one chat message, and two-decision histories only.
- The retriever is this repo's own (BM25 + bge-small, fused by rank, 7,000-character budget; 3,500 for d's notes). It tests the query shape of hook-based injection, not any product's server-side retrieval or LLM ranking.
- Synthetic repos, one fictional organization, Haiku 5.5 only.
