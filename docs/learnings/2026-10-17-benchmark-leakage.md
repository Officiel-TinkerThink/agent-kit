# Lesson: Benchmark Leakage in Code-Review Subagent Optimisation

- Date: 2026-10-17
- Area: code-review plugin, benchmark and optimisation pipeline
- Status: rules adopted; hidden test set separation still open (see section 7)

## 1. Context

The team optimises code-review subagent prompts, skills and effort levels against a benchmark of sample cases. A subagent passes when it reaches a threshold. [VERIFY: threshold value and pass metric are not written down in the benchmark README; confirm and record them here.]

## 2. What went wrong

During optimisation, the optimisation prompts carried information about the sample cases into the prompts, skills and examples. The benchmark score therefore partly measured knowledge of the test rather than capability.

A leak audit of the previous prompts found many leaks. The leaks were specific case identifiers, identifier names, literal values, root-cause phrases and scoring vocabulary.

## 3. Failure modes

- **Overfitting:** repeated tuning on the same cases.
- **Data leakage:** case-derived content enters prompts, skills, examples or reports.
- **Evaluator overfitting:** repeatedly using benchmark scores to choose changes, which exploits the scorer even with a hidden test set.

## 4. Core principle

An agent that passes the benchmark is not proven to perform the task. The pipeline must tell the two apart.

## 5. Rules adopted

1. **Separate dataset roles.** Development set (optimiser may see), validation set (limited exposure), hidden test set (no optimiser access). Do not turn a failed hidden test case into development material.
2. **Audit the whole information path.** Prompts, skills, examples, reports, logs, memory, failure feedback.
3. **Record provenance for every prompt or skill revision.** State which benchmark results informed it.
4. **Optimise on several dimensions,** not only pass rate: correctness, generalisation, robustness, constraint compliance, regression, cost, reproducibility.
5. **Change one factor at a time where feasible.** Log config, versions, hypothesis and results. [VERIFY: define what "feasible" means for this pipeline.]
6. **The optimiser is not the only judge of release readiness.** Release criteria are fixed before a run.
7. **Test the benchmark itself** with paraphrase, counterfactual, novel-composition, ablation, repeated-run and fresh-case tests.
8. **Rewrite rule.** A general rule must hold for any codebase. A rule that only makes sense with a case in view is a leak. Replace case IDs, identifiers, literals, root-cause phrases and scoring vocabulary with neutral placeholders.

## 6. Limitations

Passing these tests does not prove there is no leakage. They give stronger evidence.

## 7. Open items

- The `## Traps` heading was renamed to `## Known safe patterns` in the lens files, and the test was updated.
- A per-file leak re-check after the final edits is in progress.
- The hidden test set has not yet been separated from the development set. Treat as open, not done.

## Next lessons

Add a new section per lesson, dated, with the same headings. Index: `docs/learnings/README.md`.
