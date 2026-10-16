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

### Benchmark numbers are single-run; round 2 re-run done, trap-hit regression open
- Added: 2026-10-16. Source: side-agent caveat, parked by the user for later.
- Done 2026-10-16: round 2 re-run on the current lens (24 of 24 reports), scored by one independent scorer per case. Results are in `benchmarks/code-review/README.md`: 53 of 60 seeded defects, 4 trap hits (up from 0), 5 false positives (up from 4).
- Open: the trap-hit regression (simplicity-h1 `label_text`, simplicity-h4 `average_cents`, design-h4 duplicated retry rule, design-h7 rollback path). Decide whether to tighten the lens or the design agent, then re-run.
- Open: each number is one run with no variance estimate; repeat runs are needed before a number is used as a decision basis.
- Open: the round-1 score totals (69 of 70, 66 of 70) are one run each; the scorer output for round 1 is not kept under `results/`.
- Not started: repeat runs and the trap-hit fix.

## Done

(nothing yet)
