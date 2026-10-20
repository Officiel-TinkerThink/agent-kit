---
description: Commit-and-review cycle for a substantial code change. You implement the change yourself, run the relevant tests, commit on a feature branch, delegate a review through the code-review plugin, check each finding critically, fix the valid ones, re-review the fixes, and repeat until no actionable finding remains, then commit. Use after a substantial code change (new feature, multi-file refactor, security-relevant, data-integrity or GxP-relevant logic), or when the user asks to commit and review, or to run the review loop. Skip for one-line edits, formatting, and documentation-only changes.
argument-hint: "[spec or issue path] [base ref, default main]"
---

You implement, verify, commit and integrate. The reviewers supply findings; you decide what is valid. Never claim the code is safe or complete without evidence.

## Step 0: preconditions

- Run `git status` and `git branch --show-current`. If the branch is `main` (or the default branch), create a feature branch before the first commit: `git switch -c <type>/<short-topic>`. Never commit to the default branch, and never push or merge unless the user asked for it.
- Identify the base ref: the argument if given, else `main`. Confirm it resolves.
- Identify the spec: the path in the arguments, else a spec or issue file that clearly matches the branch name. If none is found, say so; do not guess.

## Step 0b: scope contract (write it down before cycle 1)

Decide it yourself from what the user already said, the README, CONTRIBUTING, the spec and the branch topic, using the usual best practice for that kind of change, and record it in four lines in the branch notes or the PR text. Do not ask the user for it; ask only when it cannot be inferred and a wrong guess would be costly (see "Deciding and escalating" below).

- **Goal:** what must work and who gets the impact (a working, clean feature comes before hardening).
- **In scope for findings:** the classes this cycle fixes (for example wrong results, crashes, broken contracts), and the classes that go to the backlog (for example hardening of free-text handling, rare input shapes, performance of hostile input), unless the user said otherwise.
- **Backlog file:** a path in the repo (for example `SECURITY-BACKLOG.md` or `docs/review-backlog.md`) where deferred findings are recorded with `path:line`, the scenario, the severity and the date. A deferred finding is documented, never dropped.
- **Done means:** a review cycle yields no finding in the in-scope classes. Without this line, "no defects" has no end, because reviewers never run out of ideas.

Pass the contract and the backlog path to every reviewer brief, so known limits are not reported again.

## Step 1: implement

Write the code yourself. Do not delegate edits. Keep the change to one topic.

## Step 2: verify before any commit

- Run the relevant tests with `verification-runner`, one agent per gate, in parallel: tests, lint, type check, build. Use the exact commands from the project README or CONTRIBUTING. Targeted runs are allowed for the first pass, but a full run is required before the final commit.
- Any failure: fix it yourself, re-run the failing gate, and repeat. Do not commit on red.
- Gates run only after the code is final for the cycle, and reviewers start only after the gates are green. A reviewer never reads code that fails its tests.
- Never delete or move a file during a gate or a review, including the gate's own log. Each run writes a new log name. A runner that removes a file is a defect to report, not a cleanup to accept.

## Step 3: commit

- Stage the files you changed, not everything in the tree.
- Commit message: a short subject, then what changed and why. End it with the attribution line `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`.
- Use a new commit each time. Do not amend.

## Step 4: review

- Freeze the diff first: write `git diff <base>...HEAD` to a scratch file outside the repo and review that snapshot. Do not edit source until this cycle's findings are triaged; a reviewer that reads code you are still changing reports findings about code that no longer exists.
- Size gate: a change under about 20 changed lines in one file runs the defect and spec reviewers only, and the report says which axes were skipped. Run the other axes only when the change touches them (security for auth, input, paths or secrets; architecture for new modules or dependencies).
- Run `/code-review:review <base>...HEAD [spec path]` with the scope contract and the backlog path. It fans out the focused reviewers, validates every finding, and reports only validated findings.
- Reviewers suppress items already in the backlog and report out-of-scope items as a count (`out-of-scope: <class>`), not in full. A report that repeats known limits costs tokens and hides the new findings.
- Do not run the reviewers by hand around that skill.

## Step 5: triage each finding yourself

For each validated finding, decide one of:

- **Valid and the proposed fix is reasonable:** fix it.
- **Valid but the proposed fix is wrong:** write your own fix, and say why the proposal was wrong.
- **Not valid:** reject it with the evidence (the line, the test, the rule that disproves it). Do not reject a finding just to end the loop.
- **Valid but outside the scope contract:** write it to the backlog file (location, scenario, severity, why deferred) and move on. Not a fix, not a rejection.
- **Needs a human decision** (scope, product behaviour, a compliance call): first try to decide it (see "Deciding and escalating"); stop the loop and ask only if you cannot.

Check the independent findings in parallel with `code-review:finding-validator` only when the findings do not depend on one another. Otherwise handle them in order.

**Root cause first.** A finding is evidence of a defect, not the defect. Before a fix, trace backward (caller, data flow, state, config, the test's own expectation) and ask why the failure was possible until you reach the mechanism. Name the chain: underlying defect, triggering condition, observable failure. Then pick the level of the fix:

| Level | Fix | Example |
|---|---|---|
| 1 Symptom | the error disappears, the defect stays (a catch that returns an empty result, a retry, a delay, a weakened assertion, a skipped test) | not accepted |
| 2 Immediate cause | the trigger is corrected, a deeper defect may remain (a nil check where an upstream owner should never return nil) | accepted only with a note on why the deeper cause is out of scope or unreachable |
| 3 Root cause | the contract or mechanism that allowed it is corrected (initialization and ownership, so the invalid state cannot arise) | the target |

Also search the other code paths for the same faulty assumption, and add a regression test of the invariant (it fails on the old code), not of the message. Write one test per invariant, named after it, and extend that test with a new case when a new shape appears; a new test per reproduced input makes the suite grow with every cycle.

**Severity floor.** A finding keeps the loop going only when it is in scope and medium or higher. A valid low-severity in-scope finding is fixed only when the fix is small and removes the mechanism; otherwise it goes to the backlog with its reason. Nothing valid is dropped silently. Before closing a finding ask: would this fix hold if the error showed up in another module, and what evidence shows the mechanism is gone? A fix that only makes this failure disappear is not done, and a finding is never rejected because its proposed fix is shallow: rewrite the fix.

**Is the mechanism bounded?** A level 3 fix also asks whether the mechanism can ever be finished. Recognising bad input in an open set (a pattern list for secrets in free text, a denylist, a parser for hostile formats) is unbounded: every patch adds surface and the next cycle finds a new shape. Two signs: the same component yields findings in two cycles in a row, or a fix creates the next finding. Then change the design to a bounded question (an allow-list of what may be written, structured data instead of text, a typed field instead of a string) and keep the old mechanism only as a second layer, with its limits written in the backlog.

## Step 6: fix, verify, commit

- Make the fixes. Run the same gates as Step 2.
- Commit the fixes as a new commit, with a subject that says what the review found.

## Step 7: re-review the fixes

- Run `/code-review:review <previous review head>...HEAD` so the reviewers look at the fix commits. Include the spec path again.
- Delta only: the reviewers get the fix-range diff, with the enclosing function of each changed hunk. They do not re-read whole files or code that passed the previous cycle unchanged, unless a fix touched it.
- Return to Step 5 with the new findings.

## Stop conditions

- **Done:** the latest review of the latest fix commit yields no actionable finding, meaning no in-scope finding of medium or higher that you did not reject with evidence. A fix that has not been reviewed is not done, so never report "clean" or "done" before that review has run on it.
- **Change the design, not the patch:** count findings per function (`path:function`), not per cycle. When the same function is named in findings in three consecutive cycles, stop patching it in that cycle: apply the bounded alternative (see "Is the mechanism bounded?"), move what is left of the old stream to the backlog, record the decision in the close-out, and continue. No question to the user.
- **Cap:** after four review cycles, check the stream against the scope contract on your own: findings in the in-scope classes continue the loop; the rest go to the backlog and the loop ends. If the user raised the cap, repeat that check every four cycles.
- **Escalate** only for a decision you cannot make from the evidence (see below).

## Deciding and escalating

The user wants autonomous work. Before you ask anything:

1. **Infer, and research the best practice.** Look at the repo, the spec, earlier messages and the memory notes. Then ground the options in what exists in the world, not only in what you remember: delegate research to `haiku-delegation:researcher` (`Task kind: doc-researcher`), one agent per question, in parallel and in the background, each with one clear question and the primary sources to prefer (vendor and standard documentation, the library's own docs, well-known engineering guidance; how do established tools solve this problem, what are the known failure modes). Ask for the options found with their source URLs, not for a recommendation. Keep working while they run. Then apply the common best practice and the usual tie-breakers (smallest change that meets the goal, reversible before irreversible, safer default, consistent with the surrounding code). If one option is clearly better or clearly cheaper to undo, take it, record the decision, the reason and the source URL in one or two lines, and carry on. The researchers supply evidence; the choice stays with you.
2. **Ask only when** the options are close, the choice is costly or hard to undo (data loss, public API or compliance impact, spend, outward-facing action), or it depends on a fact only the user has.
3. **When you ask, make it a decision the user can answer in one line:** the situation in two sentences; two to four options, each with its tradeoff (cost, risk, effort, what it closes off); your recommendation and why; the source URLs of the researched options when there are any, and what you will do by default if no answer comes, when that is safe. Keep working on everything that does not depend on the answer while you wait.

## Close-out

Report, in this order:

- Commits on the branch, one line each: hash and subject.
- Last review head: the commit the final review ran on, so the next agent knows what is covered.
- Tests and gates run: the command and its result, for the final commit.
- Review outcome: each validated finding with `fixed`, `rejected: <evidence>` or `escalated`.
- `Unresolved: <items>`, or `Unresolved: none`.
- Remaining risk, in plain words, that the verification did not cover.
