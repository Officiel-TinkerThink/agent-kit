---
name: review-craft
description: "Focus-mode shared craft for the code-review reviewers and the finding validator. Preloaded into them; not for direct use."
user-invocable: false
---
LENS-MARKER: review-craft v1

# Review Craft

Shared method for every code-review reviewer and for the finding validator: how to read, what counts as evidence, and what to leave out.
The agent file sets the output format and the stance; this skill adds depth and never changes them.

## Focus order

Check in this order and spend the most time on the first items:

1. Design and functional correctness: does the change do what its intent says, for every input the code accepts?
2. Failure behaviour: what happens on error, partial failure, retry and concurrent access?
3. Tests: read them only to see whether they reach the risky path. Report a test gap only where your agent file allows it. A passing suite is never proof.
4. Naming and structure: only where they hide a defect or mislead the next reader.
5. Style: last, and only when a written rule requires it.

Google's engineering practices guidance on code review asks reviewers to look at design first.
If you have a line-level nit but have not yet checked the design, your order is wrong.

## Size and pace

- About 100 changed lines is a comfortable review (Google engineering practices, small changes). Past about 400 lines, defects found per line tend to fall (SmartBear peer-review study, a vendor source).
- For a large change, work hunk by hunk, riskiest hunk first (see Reading order), and keep a list of hunks you have covered.
- Do not skim. Read each risky hunk line by line, and state which hunks or files you did not read.
- Stop when every risky hunk has been read, not when the list of findings looks long.
- Do not spend the budget on a long tail of small points while a state change or an error path is still unread.

## Reading order

1. The intent: the spec, the ticket or the stated purpose. If none was given, say so once.
2. The change overview: changed files and the commit or PR description, read as claims to check, not as facts.
3. The riskiest hunk: state changes, money, authorisation, file or network I/O, locks, retries and error paths.
4. Callers and callees of that hunk: what values pass into it and what it relies on coming out.
5. Siblings: the other functions, branches or entry points that do the same job.
6. Tests last. Tests do not test themselves. A passing suite does not prove a finding is absent, and a missing test is not a defect by itself.

## Evidence rules

- Every finding needs three things: the quoted line (or `none` for a missing requirement or missing control, then name the function where the code belongs and the terms you searched), a concrete input or sequence, and the outcome you traced.
- A function name, a comment, a docstring, a commit message or a variable name is never evidence of behaviour. Read the code under it.
- Write the trace as numbered steps: input, each branch taken, result. A trace you cannot finish is UNCLEAR, not a finding.
- Record what you searched: the symbol, the directory and the files you opened. "No caller found" means nothing without the search behind it.
- Quote the line exactly as it appears, except that a credential value is replaced by `<REDACTED>` while the key stays, as your agent file's secrets rule says. Do not paraphrase it and do not join lines.
- Name the entry point where the trace starts, such as a route, a public function or a consumer loop.
- A trace has this shape (illustrative, not a finding), written out in full:

  ```
  input: limit = 0 (passes the earlier "limit is not None" check)
  1. page_size = limit or 25 at paging.py:18 (0 becomes 25)
  2. query uses page_size at paging.py:22
  3. outcome: caller asked for 0 rows and received 25
  ```

- NOT FOUND and UNCLEAR are valid results. Use them instead of a guess.
- Never invent a line number. If you cannot cite the exact line, put the point under UNCLEAR instead of citing a nearby line.

## Diff mode and whole-file mode

Report the mode the brief names (diff or whole-file) on your FILES READ or COVERAGE line. Put no text before the `LENS:` line.

- Diff mode: report only code the change added, modified or newly exposed. Newly exposed means a private name that became public, a default value that changed, a guard that was removed, or a new input or call that reaches older code.
- Pre-existing flaws on untouched lines are out of scope even when they are real. Do not report them as findings.
- Whole-file mode: every issue in the named files is in scope. Still rank by risk and still apply the evidence rules.
- A removed line is in scope in diff mode, because removing a guard is a change. Trace what now happens without it.
- A moved line is in scope only if its old and new position differ in behaviour: a different branch, a different caller or a different order.
- A renamed symbol is in scope when a caller outside the diff still uses the old name or the old signature.
- A changed default is always newly exposed, even when the function body is untouched.

## False positives

Drop these before you write anything up:

- Pre-existing issues in code the change did not touch.
- Code that looks wrong but is correct on a trace. Trace it before you report it; a look-alike that the trace confirms is a finding at the confidence the trace supports.
- Pedantic points that a careful senior engineer on this team would not raise.
- Anything a linter, type checker, compiler or formatter already enforces.
- General quality concerns that no written rule, requirement or observable failure backs.
- A rule that is silenced in the code by an explicit, visible exemption.
- An intentional change that is part of the broader change described in the intent.
- A real issue on a line the change did not touch, even when it sits next to the change.

## Severity and confidence

Severity is one scale for every reviewer and the validator; your agent file only adds examples:

- high: wrong data saved or released, a security boundary crossed, data loss, unrecoverable state, or a regulated record changed without an audit event, on a normal path or on an input the code accepts. For the audit case report the evidence (the record, the change, the missing event); the human owner decides its weight.
- medium: a wrong result, a lost error or a harmful retry or timeout on a reachable path that needs one named extra condition (a role, a config value, an input shape, a retry, concurrency).
- low: a rare or already-guarded case, or a maintainability risk with no wrong result today. The validator never lowers a finding below low: it uses REFUTED instead.

Confidence is how sure you are that the trace holds. The finding-validator uses the rubric in its own agent file, not this scale. A reviewer reports an F line only at or above its agent file's minimum confidence and lists anything lower under UNCLEAR:

- 0: the claim is false, or you have no evidence for it.
- 25: a plausible path that you did not confirm in the code.
- 50: the path holds only if one piece of code you could not read behaves as assumed.
- 75: the path holds on every code path you read, with one small gap you can name.
- 100: the path holds and every step is traced to a quoted line.

## Comment value

- This section applies only when the main thread writes a PR comment from a finding. Reviewer and validator output keeps the format in its agent file: no labels, no fix hints, no praise there.
- Use only these labels when a comment needs one: Nit, Optional, FYI.
- A finding that breaks a rule, a requirement or an observable behaviour is never labelled Nit.
- Comment on the code, never on the author.
- Give one concrete fix hint: the line to change and what it should do instead.
- Say what breaks, and for which input, in the first sentence.
- Do not raise a blocking comment for style alone.
- Keep one comment to one defect. Two defects in one comment hide the second one when the author fixes the first.
- A comment that asks a question is a question, not a finding. Mark it FYI and say what answer would close it.
- Do not praise code in a comment. Silence on correct code is the normal state.

## Uncertainty

- If the outcome depends on code you cannot read, name the missing piece: the file, the symbol and what it would have to do.
- Never turn a guess into a finding. Put it under UNCLEAR with the question that would settle it.
- Before you call a guard absent, search the function, its callers and its callees in the material you were given.
- If the brief lacks the intent, history, spec or rule text your lens needs, say so once. Do not invent it.
- A claim that a value is always non-empty, always valid or never null is a claim to verify at the call sites, not a fact to repeat.

## Common reviewer mistakes

- Anchoring on the diff: reading only the changed lines and missing the caller that now passes a bad value.
- Trusting the author's description: "no behaviour change" is a claim to trace, not evidence.
- Stopping after the first finding: a second independent defect still counts, so keep reading the risky hunks.
- Reviewing what is easy to read instead of what is risky: spend the time on error paths, locks, I/O and state changes.
- Double counting: one root cause that breaks three call sites is one finding with three locations.
- Taking a passing test as proof: the test may never reach the failing input.
- Calling a wrong-looking line a bug without tracing it.
