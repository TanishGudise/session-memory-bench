# Pilot (G2), 2026-10-23

Model `claude-haiku-5-5`, 1 epoch. Experiment manifest `555b1d95…` (FROZEN). Billing-only corpus `adeca52c…`: 7 history sessions, 50 distilled notes (hand-labelled), 146 chunks, and a raw block of 34,076 tokens (all 7 sessions fit under the 40k cap).

What ran: billing's history and distillation, then billing's 8 tasks × 6 conditions, plus a and g on the other 10 M tasks. That makes 68 episodes. Every episode stopped `finished` and was `graded`. None was flagged, tampered, timed out or excluded, and no history attempt was discarded.

## Gates

| Gate | Needed | Pilot | |
|---|---|---|---|
| g on all 14 M tasks | ≥ 70% | 14/14 (100%) | pass |
| a on all 14 M tasks | ≤ 30% | 2/14 (14%) | pass |
| a on billing's C and D tasks | ≥ 1 of 2 | 2/2 | pass |

M tasks that a solves without memory (named in the write-up as inferable without memory): `billing-02` (the agent diagnosed the timezone flake from the code and left the cutoff alone) and `ingest-02` (it chose (source, external_id) as the identity on its own). Both were checked by hand.

## Billing, by condition (8 tasks, 1 epoch)

| Condition | M (4) | D | S-s | S-u | C | $ / episode | $ / solved | input tokens / episode | calls |
|---|---|---|---|---|---|---|---|---|---|
| a none | 1 | 1 | 1 | 1 | 1 | 0.0029 | 0.0046 | 42k | 6.9 |
| b raw | 4 | 1 | 1 | 1 | 1 | 0.0083 | 0.0083 | 189k | 4.8 |
| c retrieved | 3 | 1 | 1 | 1 | 1 | 0.0032 | 0.0037 | 47k | 5.6 |
| d distilled | 4 | 1 | 1 | 1 | 1 | 0.0031 | 0.0031 | 50k | 6.5 |
| f pull | 4 | 1 | 1 | 1 | 1 | 0.0038 | 0.0038 | 66k | 7.6 |
| g oracle | 4 | 1 | 1 | 1 | 1 | 0.0027 | 0.0027 | 38k | 6.5 |

Input tokens include cache reads (77–82% of input in every condition). The largest single request was 45,947 tokens, so none reached the 100k price tier. c's one M miss (`billing-04`, refunds) is `not_retrieved`. The hook-shaped query recalled the idempotency lesson but not the chat-only rule that refunds over $500.00 need a second approver, and only that test failed. f found the rule by searching ("refund approved_by approval refund_invoice") and passed. (Corrected 2026-10-23: the first version of this record named the idempotency lesson as the miss.)

These are single-epoch counts on one repo. They size the main run; they are not results.

## Spend

| Part | Requests | $ |
|---|---|---|
| history (7 sessions) | 65 | 0.0235 |
| distillation | 7 | 0.0068 |
| eval (68 episodes) | 433 | 0.2391 |
| pilot total | 505 | **0.2694** of the $1.50 cap |

No request was booked at its worst case (no timeouts or dropped connections).

## Projection for the main run

Per (task, epoch), all six conditions cost $0.0235 on the pilot (a 0.0026, b 0.0083, c 0.0032, d 0.0031, f 0.0038, g 0.0025).

- Main, 32 tasks × 6 conditions × 3 epochs (576 episodes): about $2.3, or $3.4 with a 1.5× margin for the other repos and longer raw blocks. That is under the $12 stage cap, so the preregistered 3 epochs stand.
- History stage (the other 19 sessions plus their distillation): about $0.1 against its $1.00 cap.
- Sonnet cross-check (8 S tasks, a/c pairs, then d): about $1.5 against its $3 cap.
