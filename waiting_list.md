# Waiting list

Open decisions and follow-ups that are parked on purpose. Add new items at the top; move an item to "Done" with the date when it is settled.

## Open

### Where should simplification findings appear in the `/code-review:review` report?
- Added: 2026-10-15. Source: side-agent note, parked by the user until development is finished.
- Situation: `simplicity-reviewer` rates most findings `low`, because redundant code gives no wrong result today. Step 5 of `plugins/code-review/skills/review/SKILL.md` puts CONFIRMED findings with severity `low` under Notes, and only `high` or `medium` under Findings. A review that finds three removable wrappers can therefore show an empty Findings section, with the simplifications in Notes where they are easy to skim past.
- Medium is reserved for copies that already differ from each other, or dead code that hides a wrong result.
- Decision needed: show simplifications in their own section (the report already has a `## Simplicity` group heading, used only for CONFIRMED at 75 or more rated medium), or keep them in Notes.
- Options to weigh when this is picked up: (a) always list CONFIRMED simplicity findings under `## Simplicity`, whatever their severity; (b) keep Notes but add a count line ("3 simplifications in Notes"); (c) leave as is.
- Not started: no code or text was changed for this item.

### Benchmark numbers are single-run and the latest lens edits are not re-benchmarked
- Added: 2026-10-16. Source: side-agent caveat, parked by the user for later.
- Situation: `benchmarks/code-review/README.md` reports round-1 and round-2 results from one run per case, with no variance estimate. The "31 of 31" stage and "69 of 70" figures could shift on a rerun. Round-2 cases were written by Haiku and audited by other agents; "clean" only means no known seeded defect. The round-1 denominator (70) does not reconcile with `truth/` (33 defects), and the round-1 and round-2 score outputs are not kept under `results/`.
- The latest simplicity-lens edits were never re-benchmarked; the re-run was blocked by the organisation spend limit (resets 12:40am Asia/Jakarta).
- Decision needed later: when the limit resets, re-run round 2 once (`python -I benchmarks/code-review/harness.py run --arm skills --cases round2 --tag=-r2after`), score it with independent semantic scorers, compare against the before-run, and add repeat runs for variance before quoting any number as a decision basis.
- Not started.

## Done

(nothing yet)
