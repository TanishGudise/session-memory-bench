# Addendum: invisible changes

Registered 2026-10-23, after the main run and before any model call for this addendum. It is separate from PREREGISTRATION.md: the main run and its analysis are unchanged, and nothing here is pooled with them. Changes after the first extension model call are listed under Amendments at the end, with date and reason.

## 1. Question

In the main run, every stale task showed the change in the code the agent read (238 of 240 S episodes saw it); no harm was detected, and no episode followed the old rule. This addendum asks the case the main run couldn't: **when a rule changed only in a later chat message, and the code doesn't show the change, does memory deliver the latest decision or the stale one?** Harm here means following the old rule.

## 2. Material

Five S-i tasks in `ext/tasks/`. Each reuses a main M task's prompt and functional tests; the rule it tests changed in a later chat message (`ext/chat.yaml`).

| Task | Based on | Old rule (in memory, from) | New rule (chat only) |
|---|---|---|---|
| billing-i1 | billing-03 | no dunning under $1.00 (billing-H4 review, 2026-08-20) | under $5.00 (chat-support-1006, 2026-10-06) |
| billing-i2 | billing-04 | second approver over $500.00 (chat-billing-0908) | over $250.00 (chat-billing-1007, 2026-10-07) |
| notify-i1 | notify-01 | quiet hours 20:00-09:00 (notify-H1 review, 2026-08-06) | 21:00-10:00 (chat-compliance-1008, 2026-10-08) |
| inventory-i1 | inventory-02 | Bramblecote cases of 6 (inventory-H2 review, 2026-08-10) | cases of 12 (chat-ops-1005, 2026-10-05) |
| inventory-i2 | inventory-03 | RNO returns-only (chat-ops-0909) | EWR returns-only, RNO ships (chat-ops-1009, 2026-10-09) |

- **Invisible.** Main's code shows neither rule. `scripts/validate_ext.py` checks each new lesson's `evidence` patterns against main's files and finds none. The new values are not common defaults.
- **Tests.**
  - `func`: the base task's functional tests (billing-i1's and notify-i1's moved so the date the code runs at, `TODAY` and `now`, falls after the change). inventory-i2 uses SFO only, so its functional tests don't depend on either rule.
  - `lesson`: the new rule. billing-i2 also keeps billing-04's two idempotency lesson tests, so its pass needs idempotency too; in the main run, 30 of 30 billing-04 episodes passed the repeated-call test and 29 of 30 the timeout test.
  - `diag`: passes only for the old rule (its exact values; for quiet hours, the end at the minute and the start at :30, as in notify-01 and the new-rule test). In billing-i1 and notify-i1 the date the code runs at falls after the change, so applying the new rule from its stated date counts as the new rule.
  - A pass needs every func and lesson test to pass, and the episode to have finished, as in the main run.
- **Solutions.**
  - `oracle`: the base task's reference solution with the new value.
  - `stale_rule`: the base task's reference solution unchanged (the old rule).
  - `visible_only`: the base task's.
- **Corpus `ext1`.**
  - Byte-identical copies of `run1`'s 26 kept sessions, their 183 distilled notes and hand labels. Spend ledgers are not copied.
  - Plus the five chat messages, frozen with `paid.py freeze-corpus --ext` (same leakage check, same 40k raw cap).
  - The new chat messages are span-labelled with the new lessons (`ext/lessons.yaml`), and the old rules keep their main labels.

## 3. Conditions and budgets

The same six conditions, agent, tools, model (`claude-haiku-5-5`) and per-episode budgets as the main run. g's notes are the task's current lessons: the new rule, plus billing.gateway-idempotency for billing-i2. **10 epochs**: 5 tasks × 6 conditions × 10 = 300 episodes. Stage `ext`, capped at **$3.00** (expected about $1.20). Paid stages run on AC power with the lid open (Amendment 1 item 4 of the main preregistration).

## 4. Gates

**G1-ext:** `scripts/validate_ext.py` reports no errors.
- Each change is dated after every source of its old rule.
- No new rule shows in main.
- Over 3 repeats:
  - the oracle passes with no diagnostic;
  - stale_rule fails a lesson test with its diagnostic firing;
  - visible_only fails a lesson test;
  - noop fails.
- Visible tests pass under UTC.
- No answer string appears in any text we wrote.

**G2-ext:** a stub end-to-end run of all five tasks × six conditions finishes with no harness error.

The model run starts only after both gates pass, a review, and a re-freeze of the manifest, which now includes `ext/`.

## 5. Outcomes and analysis (`scripts/analyze_ext.py`)

- **Per episode:** *new rule* (a pass), *old rule* (a `diag` test passed), or *other*.
- **Primary, harm.**
  - For each memory condition X in b, c, d and f: does X follow the old rule more often than no memory (a)?
  - Exact McNemar, one-sided, on (task, epoch) pairs, with discordant pairs counted on old-rule outcomes. Holm over the 4.
  - Reported with old-rule rates and Wilson 95% intervals per condition.
- **Secondary (descriptive, no tests).**
  - New-rule (pass) rates per condition and per task.
  - Outcome by what the recalled memory held, by span labels (hand labels for d's notes): new rule only, old rule only, both, or neither.
  - f's search share.
  - $ per solved task (answered calls), and the ledger total with its worst-case bookings.
- **Expected by design:** a and g have no or only the current memory; a should follow neither rule, and g should apply the new one.

## 6. Hand checks

- every a pass;
- every old-rule outcome in b, c, d or f;
- every flagged or ungraded episode;
- a random 10% (seed 0) of the rest.

A task defect found this way follows G4 of the main preregistration: the task is fixed and re-graded, or excluded with the reason, recorded as an amendment here.

## 7. Limits

- Five tasks, all built from main M tasks, so the prompts are ones the main run also used.
- Each change is carried by one chat message. PR-review comments aren't used, because adding sessions would need new history draws.
- The old rule sits in a review comment (3 tasks) or a chat message (2 tasks).
- One fictional organization, synthetic repos, Haiku only.

## Amendments

(none yet)
