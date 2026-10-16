# code-review benchmark

Corpus used to measure the `code-review` agents. 57 small cases over seven axes (round 1: 33 cases; round 2: 24 application-development cases with layered defects, decoys and a preexisting trap each). Each case is a few Python files with a written intent, spec, rule file or history digest; the answer key lives outside the case folder so a reviewer cannot read it.

| Axis | Cases | Seeded defects | Clean cases | Agent measured |
|---|---|---|---|---|
| `spec` | spec-01..04 | 9 | spec-04 | `code-review:spec-reviewer` |
| `design` | design-01..04 | 9 | design-04 | `code-review:design-reviewer` |
| `security` | sec-01..04 | 9 | sec-04 | `code-review:security-reviewer` |
| `guidance` | guidance-01..03 | 4 | guidance-03 | `code-review:guidance-reviewer` |
| `history` | history-01..03 | 2 | history-03 | `code-review:history-reviewer` |
| round 2 | bug-h1..h6, simplicity-h1..h5, design-h4..h7, spec-h4..h6, guidance-h4..h5, history-h4..h5, security-h4..h5 | see `truth/` | bug-h6, simplicity-h5, design-h7 | `design-reviewer` (bug), `simplicity-reviewer`, and the axis agents |

The table counts are for round 1; `tests/code-review/test_corpus.py` holds the per-axis totals for all 57 cases.

Layout: `cases/<axis>/<case>/` holds `spec.md` (or the rule files in `rules/`, or `history.txt` and `change.diff`) and `code/`. `truth/<axis>/<case>.json` holds `defects` (file, line, description) and `decoys` (code that looks wrong and is fine). A missing-code defect (no audit call, no owner check) is anchored to the line of the function that should contain it. `tests/code-review/test_corpus.py` checks that every cited line exists, that clean cases have no defects and that no answer key is inside a case folder.

## How a run is scored

1. Give the reviewer only the case folder (never `truth/`). One reviewer, one case, one run.
2. A seeded defect counts as found when a finding names the same root cause on the same function, even if the line differs by a few lines.
3. Every other finding is an extra. Extras are classified by the validator verdict and a human read: genuine defect, low severity, or weak or unverifiable.
4. A clean case passes when the reviewer reports `NO FINDINGS`.
5. The validator is scored separately: planted false findings aimed at the decoys must come back `REFUTED`; findings that are real must not.

## Results (Haiku 5.5 reviewers, one run per case)

| Stage | Seeded defects found | Clean cases clean | Findings | Notes |
|---|---|---|---|---|
| Baseline prompts, spec, design, security (12 cases) | 27 of 27 | 3 of 3 | 44 | 17 extras: 13 confirmed by the validator, 4 unverifiable, 0 refuted |
| After critic review and the official code-review plugin rules (15 cases, adds guidance) | 31 of 31 (earlier stage, not reproducible from `results/`) | 4 of 4 | 51 | about 88% of findings meaningful before validation; the rest low severity or unverifiable |
| Targeted re-run of the four noisiest cases after the confidence floor and input-type rules | 12 of 12 | not re-run | 23 down to 20 | weak candidates moved to `UNCLEAR` |
| History reviewer (3 cases) | 2 of 2 | 1 of 1 | 7 | over-reported one root cause several times; a one-finding-per-root-cause rule was added afterwards and not re-measured |

Validator: 6 of 6 planted false findings refuted (a sleep after the last attempt, a safe `yaml.safe_load`, an allowlisted ORDER BY, a re-raised exception, an immutable constant, a wrong quote). Real findings it checked: confirmed 13 of 17 extras and 4 of 6 seeded ones; the other 6 were `UNVERIFIABLE` because the claim depends on code outside the case (a caller, a gateway, a logging configuration). One real finding was refuted only because the reviewer's quote was `none` for missing code; the validator rule for missing-code findings was added after that and the case re-checked to `CONFIRMED`.

## Harness and later results

`python -I harness.py run|score --arm skills|baseline [--cases hard|all|round2|IDs] [--workers 8] [--tag=-name] [--agent-map axis=agent,...]` runs one reviewer per case (results in `results/<arm><tag>/`) and scores with a deterministic matcher. The matcher under-credits a finding that cites a different line, so independent semantic scoring is the reference.

- Round 1, skills versus no-skills baseline (Haiku 5.5, one run): the session scorer reported skills 69 of 70 and baseline 66 of 70 seeded defects, with 4 and 6 extras. Caveat: `truth/` holds 33 round-1 defects (spec 9, design 9, security 9, guidance 4, history 2), so the denominator of 70 is not reconciled, and the scoring output is not kept under `results/`. Treat the comparison as unverified; within noise either way.
- Round 2, before the simplicity agent (semantic scoring by independent agents; scoring output not kept under `results/`): bug 15/15, design 9/9, security 6/6, history 4/4, guidance 5/5, spec 7/9, simplicity routed through design-reviewer 1/12. Round 2 holds 97 defects (`truth/` total 130 minus round 1's 33). That gap is why `simplicity-reviewer` exists. The two spec misses were unchanged code reached by a changed call; the spec-reviewer scope rule was widened afterwards.
- Round 2 after the fixes: not measured; the run was blocked by a spend limit and its partial output was deleted.
- LENS check: every reviewer prints the marker names it sees. All 33 no-skills (baseline) reports said `LENS: none`; skills reports list the markers.

## Limits of these numbers

- Round-1 cases were hand-written, round-2 cases were built by Haiku from blueprints and audited by other agents; one run each, no variance estimate. Sources in the answer keys are concept names, not opened URLs. Treat the round-1 result as "no seeded defect was missed on this corpus", not as a recall guarantee.
- The corpus and the reviewers are the same model family, and the cases are small enough to read whole. Large diffs, unfamiliar frameworks and cross-file defects are not covered.
- Reviewers were run as Haiku 5.5 agents following the agent file as instructions, because the plugin was not installed in the measuring session; the agent files are the same text.
- Reviewers saw whole files, not diffs; the changed-lines-only rule is untested here, apart from the history cases.
- The history reviewer works from a digest the caller writes; its quality depends on that digest.
- A passing run on this corpus says nothing about GxP or 21 CFR Part 11 compliance of reviewed code; reviewers report evidence and a human owner decides.
