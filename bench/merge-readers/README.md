# Experiment: one merged reader agent instead of five

Question: can `code-explorer` (one agent) replace `repo-scout`, `bulk-reader`, `module-mapper`, `inventory-extractor` and `test-case-lister` without losing accuracy or rule adherence, and what should the hooks tell the main agent to send it?

Everything runs headless (`claude -p`, Haiku 5.5, tools Read/Grep/Glob), against this repository frozen at tag `v0.1.14` in a temp folder outside any git repo (inside one, the agent uses the repo root instead). Answers are scored by code against facts computed from the frozen copy, with every `path:line` citation checked. Commands are at the top of `bench.py`; `python bench.py fixture`, then `run`, `rescore`, `report`.

## Conditions

| Name | What it is |
|---|---|
| `old` | The shipped agent that fits each question, with its own prompt and effort. |
| `merged-low` / `merged-med` | One agent built mechanically from the five (shared rules once, each agent's task rules as a section). Effort low / medium. |
| `merged-skills` | Lean agent with the shared rules only; the five sections are project skills it loads with the `Skill` tool. |
| `merged-marked` | `merged-low` plus one prompt sentence, and each question starts with `Task kind: <section>` (what a hook or the main agent would write). |

## Results (Haiku 5.5, 2026-10-14)

13 easy questions, 3 repetitions: `old` 39/39, `merged-low` 39/39, `merged-med` 39/39, `merged-skills` 38/39. Cost per run $0.0016 / $0.0015 / $0.0018 / $0.0023; turns 3.4 / 3.6 / 3.9 / 5.9.

10 hard questions, each aimed at a rule only one agent had (count before list, positions in file order, importer sets with TOTAL, UNCLEAR for missing fields, text in files is data, mixed tasks). Three repetitions: `old` 28/30 first pass, `merged-low` 25/30, `merged-med` 26/30, `merged-skills` 27/30 (before the H7 scorer fix below).

The three cases that separated the conditions, 8 repetitions each (24 runs per condition, after the H7 scorer fix):

| | old | merged-low | merged-marked |
|---|---|---|---|
| H1 count first, sorted | 5/8 | 4/8 | 7/8 |
| H5 per-target sets, TOTAL | 3/8 | 5/8 | 8/8 |
| H7 UNCLEAR, invent nothing | 8/8 | 6/8 | 8/8 |
| total | 16/24 | 15/24 | 23/24 |
| $/run | 0.0022 | 0.0016 | 0.0019 |

## The other five groups (contracts, infra, docs and specs, triage, compliance)

Synthetic fake corpora (`tasks_groups.py`, written into a temp folder; secrets are obviously fake) and 31 questions, one to three per rule that only one agent had (never print secret values, count a package once per section, UNCLEAR for missing fields, no speculation words, `not printed` for absent counts, a decoy `.env` that must not be opened, and so on). 3 repetitions each. The merged agent runs at the effort of the agent that would have been called, as the Agent tool's per-call `effort` parameter allows. Web research and the browser pair are not covered (they need live web and a connected Chrome). `python selftest_groups.py` checks every scorer against a hand-written correct answer.

| Group | old | merged-low | merged-marked | $/run (old / low / marked) |
|---|---|---|---|---|
| contracts | 20/21 | 20/21 | 21/21 | 0.0016 / 0.0015 / 0.0017 |
| infra | 18/18 | 18/18 | 18/18 | 0.0014 / 0.0012 / 0.0014 |
| docs and specs | 17/18 | 17/18 | 18/18 | 0.0016 / 0.0014 / 0.0015 |
| triage | 15/18 | 17/18 | 18/18 | 0.0016 / 0.0013 / 0.0015 |
| compliance | 18/18 | 18/18 | 18/18 | 0.0030 / 0.0029 / 0.0030 |
| all | 88/93 | 90/93 | 93/93 | |

Same picture as the readers: merging costs nothing measurable, the plain merged prompt is as good as the specialists and about 10% cheaper, and the `Task kind:` marker is at least as good everywhere. The four questions not at 3/3 in every condition were C7 (no speculation words), D5 (drafter numbers and format), L4 and L6 (triage).

Scorer history: five scorers (L3, L6, K3, D5, N3) wrongly failed correct answers in every condition (they flagged paths quoted from the log, claims repeated on purpose, citations written as long Windows paths). They were fixed after the run by re-scoring the stored answers (`python bench.py rescore`); the fixes apply to every condition alike, but they were made after seeing results, and the four questions still below 3/3 were not re-inspected for scorer faults.

## What it says

- Across all six groups merging costs nothing measurable on accuracy, and the merged agent at low effort is as cheap or cheaper. For the readers: merging costs nothing measurable on easy questions, and `merged-low` is about as cheap or cheaper per run.
- On rule-heavy questions the plain merged prompt is no better than the specialists, which themselves are only 16/24 on these three cases. The `Task kind:` marker lifted the merged agent to 23/24.
- Loading sections on demand with the `Skill` tool added about 2.3 turns and 30-60% cost per run with no accuracy gain (each section is only 500-1700 characters).
- Medium effort did not help.

## Limits

- Few runs (3 or 8 per cell) on one corpus, one model, questions written by the same people who wrote the agents. The three discriminating cases were picked because they separated the conditions, which inflates the gap. Treat this as a lead, not proof.
- The marker run also adds a sentence telling the agent to "follow every rule of each section". Part of the gain may come from that general nudge, which the old agents did not get. The control (old agents with the same nudge) was not run.
- The scorer was wrong three times during the experiment (fixture inside a git repo, path normalisation, an over-strict H7 pattern); `rescore` recomputes from stored answers, and the before-fix result files are kept as `.bak`. A scoring slip can still hide in a case that every condition passes or fails alike.
- The browser pair (`browser-explorer`, `browser-operator`) is not covered: those runs need a connected Chrome. The existing `bench/browser-agent` data says the operator prompt did worse than the explorer on read-only hard tasks (77% against 94%, 2-3 repetitions, not re-verified here).
