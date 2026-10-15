# Benchmark cases: agent failures kept as tests

When a subagent of this kit fails a task (breaks one of its rules, misses what was asked) and the failure is annotated, the failure becomes a **case**: a small synthetic task that the failed answer would not pass. Cases pile up on the `bench-cases` branch, so every improvement of an agent is measured against every failure we have seen so far.

This is separate from `/agent-eval:report-issue`, which reports errors of the plugins themselves (hooks, scripts) to GitHub issues.

## Use it on another device or as another user

    git fetch origin bench-cases
    git checkout bench-cases
    python bench/cases/run_cases.py validate          # no model calls
    python bench/cases/run_cases.py list
    python bench/cases/run_cases.py run --reps 3     # Haiku 5.5 through `claude -p`, about a cent per run; stops at --budget (default 2.0 USD)
    python bench/cases/run_cases.py report           # pass rate per case and kit version, from bench/cases/results/ (kept on this device)

The run uses the agent definitions in `plugins/*/agents` of the checked-out branch. To measure a newer kit version, merge `main` into `bench-cases` (`git merge origin/main`); the cases stay, the agents change, and `report` shows both versions side by side. Needs `claude` on the PATH, Python 3.10+.

## Add a case

1. Annotate the failure the usual way (the main model calls the `annotator`); note the annotation id (`ann-...` in `<KIT_DATA>/eval/annotations.jsonl`).
2. Rebuild the failure with **synthetic** material: a prompt and a few fixture files that make an agent fail the same way. Never copy a real project file, the real prompt, a secret or personal data; the branch is public.
3. Capture it:

       python bench/cases/capture_case.py --annotation ann-... --slug short-words --prompt-file prompt.txt --fixture-dir ./fixture \
           --rule-broken "<the rule text the agent broke>" --expect-all "<text a correct answer has>" --forbid "<text the failed answer had>" \
           --confirm-no-sensitive-data

   Nothing is written when the case is invalid, has checks that cannot fail, or the privacy scan finds a secret-shaped text, a home path or an e-mail address.
4. Run it (`run_cases.py run --cases BC-... --reps 3`). A case that the agent already passes is still kept as a regression guard; say so in `--note`.
5. Commit the file in `bench/cases/cases/<agent>/` to `bench-cases` (or open a pull request into it). Set `status` to `fixed` and `fixed_in` once an agent change makes it pass reliably.

## Case file (`bench-case/1`)

`id` (`BC-<agent>-<slug>`), `agent`, `title`, `found_in` (kit version), `status` (`open` or `fixed`, with `fixed_in`), `origin` (annotation id or manual), `failure` (`code`, `rule_broken`, `symptom`), `prompt` (`{kit_data}` becomes a temp folder), `fixture.files` (at most 20 files, 20 KB, relative paths), `checks` (`expect_all`, `expect_any`, `forbid`, `require_regex`, `forbid_regex`, `min_turns`), optional `allow` (tool permissions for the run) and `note`. The format is checked by `casefmt.py`; `tests/bench/test_bench_cases.py` checks the tools.
