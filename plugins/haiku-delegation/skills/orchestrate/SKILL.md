---
description: Orchestrator-first execution for substantial multi-step work. Decomposes the task into independent units, delegates each unit to a Haiku 5.5 kit agent, launches independent units in parallel in one message, keeps the main thread for edits, integration and verification, and owns the final result. Use at the start of any task with more than one independent step, codebase exploration, log or test-output triage, spec or document extraction, dependency or advisory checks, compliance evidence gathering, or whenever the user says delegate, parallelize, orchestrate or use subagents. Skip for a single-line answer or one edit to a file already in view.
argument-hint: "[task description]"
---

You are the orchestrator. Your job is to decompose, delegate, parallelize, keep working, integrate and verify, and own the result. Writing code is the one thing you do yourself. Start the first reply with the decomposition table or the first Agent call; no preamble.

## Step 0: decide whether to run this procedure

- One edit to a file already in view, or a question answerable from a file already in context: do it inline, and say which of these applies in the close-out line.
- Anything else: run Steps 1 to 6.

## Step 1: decompose

Write the units as a table before any call. A unit is the smallest piece that cannot be split further: one question or one deliverable with one result.

| # | Unit | Agent and Task kind | Inputs (absolute paths) | Expected output | Depends on |
|---|---|---|---|---|---|

Rules for the table:
- One unit per row. A row with "and then", several deliverables, or a numbered list is two rows.
- Mark which rows are independent. Independent rows run together.
- Writing code, design decisions, root-cause analysis, and security, GxP or validation judgement are not rows. They stay with you.

## Step 2: delegate, in parallel

- Launch every unblocked row in one message, as multiple Agent calls. Cap a wave at 8 agents; start the next wave as results arrive.
- Use the full agent name `<plugin>:<agent>`. The kit agents and their Task kinds are in `SUBAGENTS.md` (or the session policy). Brief shape:
  - First line: `Task kind: <kind>` (required for `code-explorer` and `contracts-reader`, and for the topic agents named in the policy).
  - One precise question. No numbered steps.
  - Absolute paths and the repository facts the agent needs.
  - The output you want: terse bullets or a table with `path:line`.
  - Exclusions: real `.env*` files, caches, build output, anything holding secrets.
- For a non-kit subagent (general-purpose, Explore, Plan) always pass `model: "haiku"`. A hook blocks the call otherwise.
- Pass `effort: medium` or `high` on the Agent call only for the kinds that need it (see the policy table).

## Step 3: keep working while agents run

- Do the next independent piece: read the rows that have no agent yet, prepare test commands, plan the integration order, draft the edit.
- Do not poll. A background agent notifies you when it finishes. Wait only when the next action needs its result.

## Step 4: integrate and verify

- Before you edit from any agent's `path:line` claim, run `compliance-lister` with `Task kind: citation-verifier` on the claims you will rely on, or re-read the cited lines yourself.
- Check totals and counts against the source. An agent's total is a claim until you recount it.
- Resolve conflicts between agents' outputs yourself. Name the chosen answer and the reason.
- After any batch of code edits, run the project's gates with `verification-runner`, one agent per gate, in parallel: tests, lint, types, build. Use the commands from the project README or CONTRIBUTING.
- Never claim success without evidence. Each claim in the final message cites the command and its result.

## Step 5: handle blockers without stalling

- A failed or partial agent result: fix the brief (narrow the question, add the missing path) and re-run that unit. Two failures on the same unit: stop that unit and say so.
- An unblocked unit that does not depend on the blocker keeps running.
- If a result was wrong and you verified it yourself, call `agent-eval:annotator` once, in the background, with the agent id, what was wrong, what you expected, and how you found out.

## Step 6: close out

End with these lines, in this order:

- `Handoffs: <agent x count>` or `Inline: <reason>`.
- `Verified: <gate and command>: <result>`, one line per gate run.
- `Unresolved: <items>`, or `Unresolved: none`.
- `Annotated: <agent_type> <outcome>` or `Annotate: skipped, <reason>`, when relevant.

## Never delegate

Debugging and root cause, architecture and design decisions, security and authorization changes, GxP and 21 CFR Part 11 conclusions, validation conclusions, upgrade-safety calls, and every edit. Agents supply evidence; you make the call.

## Related

For a substantial code change that must be committed and reviewed, continue with the `haiku-delegation:review-fix-cycle` skill after the edits are verified.
