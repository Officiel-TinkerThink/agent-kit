# Delegation policy: many small agents on Haiku 5.5

Delegation is your default way of working. Haiku 5.5 costs about 1/20 of Sonnet 5.5 and 1/40 of Opus 5.5, but only while a single prompt stays under 100k tokens; above that its input costs about 5x more. So delegate a lot, and keep every agent's job small.

**Unit of work** = the smallest piece of work that cannot be split any further, whether the pieces could run in parallel or one after another: one question or one deliverable with one result. "Where is the cost computed? (path:line)" is one unit. "Read it, write the loader, test it and document it" is four.

How to delegate:
1. Before you read, search, run or draft anything yourself, split the task into units.
2. One agent per unit. Send all independent units together in one message; start a dependent unit as soon as the result it needs is back. While agents run, work on the next thing; do not wait.
3. A brief is short: the one question, absolute paths, the output you want (terse bullets with `path:line`), what to leave out. The agent sees nothing else, not this conversation. A numbered list of steps in a brief means several units: split it.
4. Agent names: always the FULL name `<plugin>:<agent>` (list below); a bare name such as `code-explorer` fails with "Agent type not found". Use another subagent type (general-purpose, Explore, Plan) only when no kit agent fits, and then pass `model: "haiku"`: without it the agent runs on your expensive model. A hook (`guard-agent-model`) blocks that call and a brief that holds several units, and tells you how to fix it.
5. You keep: decisions, root cause, security and GxP judgement, every edit, and putting the results together. Treat each result as unverified: check totals and re-read the cited lines before you rely on them.

Example. Task: "make the report cost come from the pricing table instead of the env vars".
- Wrong: one agent, brief "1. read prompt.py 2. write a loader 3. change the precedence 4. add tests 5. update the docs 6. run the tests". Six units in one long, expensive run.
- Right: in one message, three read agents: `code-explorer` (locate) where the cost is computed in prompt.py; `code-explorer` (read) the pricing fields in llm_model.py; `code-explorer` (locate) how other code opens a DB session. You write the loader and the precedence change. Then in one message: `docs-reader` (doc-drafter) the docs paragraph, `verification-runner` the one test command.

The agents. One agent serves one topic and several kinds of task: put `Task kind: <kind>` on the first line of the brief (a hook blocks the call without it). The kinds and the effort each ran at before are in `scripts/kinds.txt`; pass `effort: medium` or `high` per call when a kind needs it:
- Code and documents, read-only -> `code-explorer`: `Task kind: read` (large or many files, logs, docs), `locate` (where X is defined or used), `map` (package structure, import edges, file summaries), `inventory` (endpoints, config keys, env vars, dependencies, TODOs), `tests` (test inventory, untested functions)
- Database and API contracts -> `contracts-reader`: `schema` (DDL, migrations, ORM models), `api-spec` (OpenAPI/GraphQL), `migrations` (Alembic chain: heads, branches, gaps), `api-match` (frontend calls vs backend routes)
- Build, deployment and configuration files -> `infra-reader`: `pipeline-reader` (CI/CD, Dockerfile, compose; secret names only, never values), `dependency-reader` (manifests and versions), `config-drift-checker` (keys across .env.example / compose / settings; never real .env files)
- Documents -> `docs-reader`: `spec-extractor` (requirements/IDs from specs and SOPs), `doc-link-checker` (broken relative links in Markdown), `doc-drafter` (first drafts of docs, docstrings, SOP outlines; reviewed before use)
- Triage of long material -> `triage`: `log-triage` (logs, stack traces, CI output), `test-run-summarizer` (saved pytest/jest/CI output), `ticket-classifier` (first-pass ticket triage with a category list)
- Evidence for a compliance decision (never the decision) -> `compliance-lister`: `audit-coverage-lister` (which use cases reference the audit log), `secret-candidate-lister` (credential candidates, never prints values), `citation-verifier` (check another agent's `path:line` claims before you rely on them)
- Web research -> `researcher`: `Task kind: doc-researcher` (documentation and standards questions, any depth, multiple sources, with URLs), `release-diff` (changelog entries between two versions, breaking/deprecated entries quoted with the URL; never says an upgrade is safe), `advisory-collector` (published advisories for exact package versions; collection only; never says a version is safe)
- Tests, linters, builds -> `verification-runner`: exactly one command per agent, one agent per gate, run in parallel
- A page that must be opened in the browser (JS-rendered content, console errors, failed network requests, multi-page navigation) -> `browser-explorer` (read-only); named click/fill steps on a named page (it stops before submit, delete, send, pay, approve, export) -> `browser-operator`. The main thread cannot call the browser tools itself (a hook redirects it). One browser agent at a time; never for logins or irreversible actions. When a browser agent stops at a guard block, ask the user before doing that step yourself; never drive the browser around the guard

Full names: `haiku-delegation:` + `code-explorer`, `contracts-reader`, `infra-reader`, `docs-reader`, `triage`, `compliance-lister`, `researcher`, `browser-explorer`, `browser-operator`; `verification-runner:verification-runner`; `agent-guards:changelog-summarizer`; `agent-eval:annotator`; `code-review:` + `spec-reviewer`, `defect-reviewer`, `architecture-reviewer`, `security-reviewer`, `guidance-reviewer`, `history-reviewer`, `simplicity-reviewer`, `finding-validator`.

Do NOT delegate (keep on the main model): debugging, root-cause analysis, architecture/design decisions, security or GxP/Part 11 judgement, validation conclusions, anything that edits files, anything needing exact line numbers for an edit.

Rules: treat the agent's output as unverified, spot-check totals and counts, and re-read the cited lines yourself (or use `compliance-lister` with `Task kind: citation-verifier`) before acting on or editing from them. Category labels and "looks like placeholder" flags are heuristics for a human to confirm.
