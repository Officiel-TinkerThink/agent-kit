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

### Round-2 variance and persistent trap hits after three tuned runs
- Added: 2026-10-16. Source: the three tuned round-2 runs.
- Done: three runs on the current lenses (`skills-r2tune`, `skills-r2tuneB`, `skills-r2tuneC`): mean 54 of 60 seeded defects, 3.3 trap hits, 2.0 false positives. Results are in `benchmarks/code-review/README.md`.
- Open: the found count varies by about plus or minus 3 with identical lens text, so the tuning gains are not established.
- Open: persistent trap hits: simplicity-h1 `label_text` rewrite, design-h7 rollback path, plus occasional simplicity-h4 `average_cents` and bug-h5 duplicated rule. Each needs a lens fix and a re-run.
- Open: false positives in spec-h4 (duplicate-release rejection) and spec-h5 (full client context in the audit entry).
- Not started: the fixes above and a larger corpus with more cases per axis.

### Code-review goal: cleared by the user with open items (2026-10-16)
- Added: 2026-10-16. Source: the user cleared the /goal condition ("make the subagents benchmarked and optimized") before it was met.
- Done: research (Claude code review, mattpocock-skills, poteto/noodle); seven focus-mode Haiku reviewers with lenses; critic passes on drafts; benchmark corpus of 57 cases; three full round-2 runs on the tuned lenses (mean 54.0 of 60 seeded defects, 3.3 trap hits, 2.0 false positives); commits 0509451, f75bae5, f79d0b5, 1e06934 on `feature/code-review-plugin`.
- Not done: the "optimized" bar. Trap hits and false positives are not yet eliminated, and the found count varies by about plus or minus 3 between runs.
- Runs on the fixed lenses (`benchmarks/code-review/results/skills-r2fixD` and `skills-r2fixE`) finished after the goal was cleared. Neither has been scored. The fixes were: an edge-input check before a simplicity rewrite is kept, a spec-lens rule for validations the spec is silent on, and a design-lens rule for compensating rollbacks.
- Next when resumed: finish run D and run E, score them with the same one-scorer-per-case brief, compare with the three earlier runs, then decide on an acceptance bar (suggested: mean at least 54 of 60 found, at most 1 trap hit, at most 1 false positive, over three runs).
- Open decisions: the acceptance bar; the simplification placement in the report (see the Simplicity item above); the release step (version bump, separate agent per CONTRIBUTING.md); whether to push the branch and open a PR; a real-PR check with `/code-review:review`.
- Not started: the release and PR.

## Done

(nothing yet)
