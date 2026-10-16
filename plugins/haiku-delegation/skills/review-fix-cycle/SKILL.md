---
description: Commit-and-review cycle for a substantial code change. You implement the change yourself, run the relevant tests, commit on a feature branch, delegate a review through the code-review plugin, check each finding critically, fix the valid ones, re-review the fixes, and repeat until no actionable finding remains, then commit. Use after a substantial code change (new feature, multi-file refactor, security-relevant, data-integrity or GxP-relevant logic), or when the user asks to commit and review, or to run the review loop. Skip for one-line edits, formatting, and documentation-only changes.
argument-hint: "[spec or issue path] [base ref, default main]"
---

You implement, verify, commit and integrate. The reviewers supply findings; you decide what is valid. Never claim the code is safe or complete without evidence.

## Step 0: preconditions

- Run `git status` and `git branch --show-current`. If the branch is `main` (or the default branch), create a feature branch before the first commit: `git switch -c <type>/<short-topic>`. Never commit to the default branch, and never push or merge unless the user asked for it.
- Identify the base ref: the argument if given, else `main`. Confirm it resolves.
- Identify the spec: the path in the arguments, else a spec or issue file that clearly matches the branch name. If none is found, say so; do not guess.

## Step 1: implement

Write the code yourself. Do not delegate edits. Keep the change to one topic.

## Step 2: verify before any commit

- Run the relevant tests with `verification-runner`, one agent per gate, in parallel: tests, lint, type check, build. Use the exact commands from the project README or CONTRIBUTING. Targeted runs are allowed for the first pass, but a full run is required before the final commit.
- Any failure: fix it yourself, re-run the failing gate, and repeat. Do not commit on red.

## Step 3: commit

- Stage the files you changed, not everything in the tree.
- Commit message: a short subject, then what changed and why. End it with the attribution line `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`.
- Use a new commit each time. Do not amend.

## Step 4: review

- Run `/code-review:review <base>...HEAD [spec path]`. It fans out the focused reviewers, validates every finding, and reports only validated findings.
- Do not run the reviewers by hand around that skill.

## Step 5: triage each finding yourself

For each validated finding, decide one of:

- **Valid and the proposed fix is reasonable:** fix it.
- **Valid but the proposed fix is wrong:** write your own fix, and say why the proposal was wrong.
- **Not valid:** reject it with the evidence (the line, the test, the rule that disproves it). Do not reject a finding just to end the loop.
- **Needs a human decision** (scope, product behaviour, a compliance call): stop the loop and ask the user.

Check the independent findings in parallel with `code-review:finding-validator` only when the findings do not depend on one another. Otherwise handle them in order.

## Step 6: fix, verify, commit

- Make the fixes. Run the same gates as Step 2.
- Commit the fixes as a new commit, with a subject that says what the review found.

## Step 7: re-review the fixes

- Run `/code-review:review <previous review head>...HEAD` so the reviewers look at the fix commits. Include the spec path again.
- Return to Step 5 with the new findings.

## Stop conditions

- **Done:** a review cycle yields no actionable finding. Findings you rejected with evidence count as not actionable.
- **Escalate:** a finding needs a human decision, or four review cycles have run. Report the open findings with the evidence and ask the user how to proceed. (Four cycles is this skill's cap; a higher cap is the user's call.)

## Close-out

Report, in this order:

- Commits on the branch, one line each: hash and subject.
- Tests and gates run: the command and its result, for the final commit.
- Review outcome: each validated finding with `fixed`, `rejected: <evidence>` or `escalated`.
- `Unresolved: <items>`, or `Unresolved: none`.
- Remaining risk, in plain words, that the verification did not cover.
