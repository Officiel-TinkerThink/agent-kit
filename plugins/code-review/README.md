# code-review

Focused, read-only Haiku 5.5 code-review agents plus an independent validator, and a skill that runs them in parallel and reports only validated findings. One agent has one focus, so a small model keeps a narrow checklist instead of a vague "review this".

## What a review should focus on

In priority order: (1) correctness against the written spec; (2) vulnerabilities in the changed code; (3) design weaknesses and bugs that cause a concrete failure (design-reviewer covers both; there is no separate bug reviewer); (4) the project's own written rules (CLAUDE.md, CONTRIBUTING, comments that say what must not change); (5) regressions the history reveals. Not worth reporting: style, anything a linter, type checker or compiler catches, pre-existing issues, speculative issues with no failure scenario, test-coverage wishes unless a rule requires them.

## Agents

Always call them by the full name.

| Agent | One focus | Input it needs | Effort |
|---|---|---|---|
| `code-review:spec-reviewer` | Code against its spec: missing, partial, wrong, unrequested | spec path, code or diff | high |
| `code-review:design-reviewer` | Swallowed exceptions, hidden global state, non-idempotent retries, missing transaction boundaries, hardcoded hosts, duplicated rules, ignored parameters | intent line, code or diff | high |
| `code-review:security-reviewer` | OWASP Top 10 and CWE checklist, source-to-sink tracing, missing controls (auth, audit trail) | intent line, code or diff | high |
| `code-review:guidance-reviewer` | CLAUDE.md, CONTRIBUTING, standards, guidance comments in the code | rule file paths, code or diff | high |
| `code-review:history-reviewer` | Guards, limits and review comments from earlier commits that the change undoes | history digest, change, code | high |
| `code-review:simplicity-reviewer` | Added logic a simpler form replaces with identical behaviour: boolean ladders, no-op try/except, dead branches, one-implementation abstractions, flags every caller sets the same way, copied validators | intent line, code or diff | high |
| `code-review:finding-validator` | One finding: CONFIRMED, REFUTED or UNVERIFIABLE with evidence and a 0 to 100 confidence | the finding and the file paths | high |

Every reviewer: neutral stance, `NO FINDINGS` is a valid answer, every finding carries a quoted code line and a concrete scenario, candidates below a confidence floor go to `UNCLEAR`, no verdicts on GxP or Part 11 compliance. Tools are `Read, Grep, Glob`; nothing edits or runs code.

## Use

`/code-review:review <git range | branch | PR | path> [spec path]` runs the eligibility check, pins the diff and the spec, fans the reviewers out in waves of at most 8 agents at a time, validates every finding with one validator per finding, and reports:

- findings (validator CONFIRMED, confidence 75 or more, severity high or medium), grouped by axis and never merged across axes;
- Notes (CONFIRMED but low severity or confidence 50);
- Unverifiable (the claim depends on code, config or a caller the validator could not read);
- Filtered (REFUTED findings, and any CONFIRMED finding the main model dropped, each with a reason).

To call one agent directly, put the intent and the absolute paths in the brief. The `finding-validator` gets one finding per call.

## Where the design comes from

- Anthropic's `code-review` plugin: parallel specialist reviewers, one validator per issue, a 0/25/50/75/100 confidence rubric, a list of false positives to skip (pre-existing issues, linter-catchable issues, intentional changes, lines the change did not touch), an eligibility check before and after.
- `mattpocock/skills` `code-review`: Standards and Spec as separate axes that are never merged, a documented standard overriding the smell baseline.
- `poteto/noodle` `adversarial-review` and `review`: one lens per reviewer, a verdict plus a judgement step that rejects style-over-substance findings.
- Published evidence on small-model review: a separate verification pass is the best-supported precision lever; self-reflection loops raised recall but lowered signal-to-noise; "bug present" framing raised false positives.

Measured results, the corpus and the limits of those numbers are in `benchmarks/code-review/README.md`.

## Known limits

- Reviewers see only the files they are given; whether a guard exists in a caller, gateway or database trigger is reported as `UNVERIFIABLE`, not guessed.
- The history reviewer depends on a digest the caller writes (`git log` with the touched hunks and earlier PR comments).
- Simplification findings are `low` and so land in Notes, not Findings. How to show them is parked in `waiting_list.md`.
- The corpus is 57 small cases, written by Haiku builders and audited by other agents; most runs are single. Real-PR-sized diffs are not measured. A "clean" case means no known seeded defect, not proven clean.
- The last edits to the simplicity lens (traps from an adversarial test, validator wording) were not re-benchmarked: the re-run was blocked by an organisation spend limit. Re-run `python -I benchmarks/code-review/harness.py run --arm skills --cases round2 --tag=-r2after` and score it before relying on them.
- Tested with `--plugin-dir`; a marketplace install was not tested.
