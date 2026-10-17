# code-review benchmark

Corpus used to measure the `code-review` agents. 57 small cases over seven axes (round 1: 33 cases; round 2: 24 application-development cases with layered defects, decoys and a preexisting trap each). Each case is a few Python files with a written intent, spec, rule file or history digest; the answer key lives outside the case folder so a reviewer cannot read it.

| Axis | Round-1 cases | Round-1 seeded defects | Round-2 cases | Round-2 seeded defects | Agent measured |
|---|---|---|---|---|---|
| `spec` | 7 (spec-01..04, spec-h1..h3) | 18 | spec-h4..h6 | 9 | `code-review:spec-reviewer` |
| `design` | 7 (design-01..04, design-h1..h3) | 18 | design-h4..h7 | 9 | `code-review:architecture-reviewer` (design axis is a hypothesis; its seeds may include defect-type items, measure before trusting) |
| `security` | 7 (sec-01..04, sec-h1..h3) | 18 | security-h4..h5 | 6 | `code-review:security-reviewer` |
| `guidance` | 6 (guidance-01..03, guidance-h1..h3) | 10 | guidance-h4..h5 | 5 | `code-review:guidance-reviewer` |
| `history` | 6 (history-01..03, history-h1..h3) | 6 | history-h4..h5 | 4 | `code-review:history-reviewer` |
| `bug` | - | - | bug-h1..h6 | 15 | `code-review:defect-reviewer` |
| `simplicity` | - | - | simplicity-h1..h5 | 12 | `code-review:simplicity-reviewer` |

Round 1: 33 cases, 70 seeded defects. Round 2: 24 cases, 60 seeded defects. Clean cases (no seeded defect) are listed in `truth/`: round 2 has bug-h6, simplicity-h5 and design-h7. `tests/code-review/test_corpus.py` checks the 57 cases.

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
- Round 2 after the fixes (current lens and agent files, one run, semantic scoring by one independent scorer per case; 24 of 24 reports produced):

| Axis | Seeded defects found | Trap hits | False positives | Notes |
|---|---|---|---|---|
| bug (h1-h6) | 15 of 15 | 0 | 0 | one real extra in bug-h2 not in the key (unverified) |
| simplicity (h1-h5) | 7 of 12 as findings (10 of 12 counting UNCLEAR-only mentions) | 2 (h1 `label_text`, h4 `average_cents`) | 1 (h2 out-of-focus note) | simplicity-h1 missed `archive_path`; simplicity-h4 TaxMemo only partial |
| design (h4-h7) | 9 of 9 | 2 (h4 duplicated retry rule, h7 rollback path) | 0 | real extras not in the key (unverified): h4 linear sleep, h5 stop/start sentinel, h7 two |
| spec (h4-h6) | 7 of 9 | 0 | 2 (h4 duplicate-release rejection, h5 full client context) | spec-h6 `dose_calc` only an UNCLEAR note |
| guidance (h4-h5) | 5 of 5 | 0 | 0 | |
| history (h4-h5) | 4 of 4 | 0 | 0 | |
| security (h4-h5) | 6 of 6 | 0 | 2 (h4 symlink note, h4 unauthenticated user object) | |

Total: 53 of 60 seeded defects as findings (56 of 60 counting UNCLEAR-only mentions); 4 trap hits; 5 false positives. Compared with the before-run: seeded defects went from 47 of 60 to 53 of 60, simplicity from 1 of 12 to 7 of 12 (the simplicity agent was added), and guidance lost its one false positive. Trap hits went from 0 to 4 and false positives from 4 to 5. The trap-hit increase is a regression to address; it rests on one run per case.

- Round 2 after the trap-hit tuning (`results/skills-r2tune/`, one run, one independent scorer per case, same brief as above):

| Axis | Seeded defects found | Trap hits | False positives | Notes |
|---|---|---|---|---|
| bug (h1-h6) | 15 of 15 | 0 | 0 | bug-h3 matched on root cause, mechanism weaker |
| simplicity (h1-h5) | 6 of 12 | 1 (h4 `average_cents` guard) | 0 | simplicity-h1 missed `archive_path`; simplicity-h3 missed the third weight copy (excluded on purpose by the spec) |
| design (h4-h7) | 9 of 9 | 1 (h7 rollback path) | 0 | the rollback exemption added to the lens did not stop the h7 hit |
| spec (h4-h6) | 7 of 9 | 1 (h5 pre-existing purge path) | 2 (h4 duplicate-release, h5 full client context) | |
| guidance (h4-h5) | 4 of 5 | 0 | 0 | h4 missed the integer-cents rule outside billing; it was found in the first after-run |
| history (h4-h5) | 4 of 4 | 0 | 0 | |
| security (h4-h5) | 6 of 6 | 0 | 0 | |

Tuned total: 51 of 60 seeded defects, 3 trap hits, 2 false positives. Against the untuned after-run (53 of 60, 4 trap hits, 5 false positives), the tuning lowered the trap hits and false positives by one run each and cost two defects, one of them (guidance-h4) found in the earlier run but not this one. Run-to-run variance on one case is at least that large, so these differences are not statistically established. Two of the four original trap hits (simplicity-h4, design-h7) are still hit.

- Round 2 after the second tightening (simplicity reviewer now reports unseen-caller findings at confidence 55; `results/skills-r2tuneB/`, `skills-r2tuneC/` and the second `skills-r2tuneB` run; three runs, one independent scorer per case):

| Run | Seeded defects found | Trap hits | False positives |
|---|---|---|---|
| tuned, first (`skills-r2tune`) | 51 of 60 | 3 | 2 |
| B (`skills-r2tuneB`) | 54 of 60 (56 counting UNCLEAR-only mentions) | 4 | 2 |
| C (`skills-r2tuneC`) | 57 of 60 | 3 | 2 |
| mean of the three | 54.0 of 60 | 3.3 | 2.0 |

The found count varies by about ±3 between runs with identical lens text. The trap hits recur: simplicity-h1 (`label_text` rewrite changes behaviour for None), design-h7 (rollback path), and in one run each simplicity-h4 (`average_cents` guard) and bug-h5 (duplicated inclusive-day rule). The false positives come from spec-h4 and spec-h5. Simplicity recall ranges from 6 to 11 of 12 across runs.
- Status: the agents are benchmarked on 60 seeded defects with three runs each, but the variance is larger than the gap between the tuned lens versions. The trap hits are not yet eliminated. This is not an optimised end state.
- LENS check: every reviewer prints the marker names it sees. All 33 no-skills (baseline) reports said `LENS: none`; skills reports list the markers.

## Limits of these numbers

- Round-1 cases were hand-written, round-2 cases were built by Haiku from blueprints and audited by other agents; one run each, no variance estimate. Sources in the answer keys are concept names, not opened URLs. Treat the round-1 result as "no seeded defect was missed on this corpus", not as a recall guarantee.
- The corpus and the reviewers are the same model family, and the cases are small enough to read whole. Large diffs, unfamiliar frameworks and cross-file defects are not covered.
- Reviewers were run as Haiku 5.5 agents following the agent file as instructions, because the plugin was not installed in the measuring session; the agent files are the same text.
- Reviewers saw whole files, not diffs; the changed-lines-only rule is untested here, apart from the history cases.
- The history reviewer works from a digest the caller writes; its quality depends on that digest.
- A passing run on this corpus says nothing about GxP or 21 CFR Part 11 compliance of reviewed code; reviewers report evidence and a human owner decides.
