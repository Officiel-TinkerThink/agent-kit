# Cost policy: delegate cheap work to Haiku 5.5

Haiku 5.5 is ~20x cheaper than Sonnet 5.5 and ~40x cheaper than Opus 5.5 (at prompts up to 100k tokens; still cheaper above). Before doing a task yourself, ask: is it read-heavy, bounded and low-risk? If yes, delegate it with the Agent tool.

Delegate (Agent tool with `subagent_type` = one of the agents below (the plugin prefix is optional), or `model: "haiku"` on any other subagent call). One agent serves one topic and several kinds of task: put `Task kind: <kind>` on the first line of the brief (a hook blocks the call without it). The kinds and the effort each ran at before are in `scripts/kinds.txt`; pass `effort: medium` or `high` per call when a kind needs it:
- Code and documents, read-only -> `code-explorer`: `Task kind: read` (large or many files, logs, docs), `locate` (where X is defined or used), `map` (package structure, import edges, file summaries), `inventory` (endpoints, config keys, env vars, dependencies, TODOs), `tests` (test inventory, untested functions)
- Database and API contracts -> `contracts-reader`: `schema` (DDL, migrations, ORM models), `api-spec` (OpenAPI/GraphQL), `migrations` (Alembic chain: heads, branches, gaps), `api-match` (frontend calls vs backend routes)
- Build, deployment and configuration files -> `infra-reader`: `pipeline-reader` (CI/CD, Dockerfile, compose; secret names only, never values), `dependency-reader` (manifests and versions), `config-drift-checker` (keys across .env.example / compose / settings; never real .env files)
- Documents -> `docs-reader`: `spec-extractor` (requirements/IDs from specs and SOPs), `doc-link-checker` (broken relative links in Markdown), `doc-drafter` (first drafts of docs, docstrings, SOP outlines; reviewed before use)
- Triage of long material -> `triage`: `log-triage` (logs, stack traces, CI output), `test-run-summarizer` (saved pytest/jest/CI output), `ticket-classifier` (first-pass ticket triage with a category list)
- Evidence for a compliance decision (never the decision) -> `compliance-lister`: `audit-coverage-lister` (which use cases reference the audit log), `secret-candidate-lister` (credential candidates, never prints values), `citation-verifier` (check another agent's `path:line` claims before you rely on them)
- Web and documentation research (any depth, multiple sources) -> `doc-researcher`
- A page that must be opened in the browser (JS-rendered content, console errors, failed network requests, multi-page navigation) -> `browser-explorer` (read-only); named click/fill steps on a named page (it stops before submit, delete, send, pay, approve, export) -> `browser-operator`. The main thread cannot call the browser tools itself (a hook redirects it). One browser agent at a time; never for logins or irreversible actions. When a browser agent stops at a guard block, ask the user before doing that step yourself; never drive the browser around the guard
- Changelog between two versions (breaking/deprecated entries, quoted with URL; never says an upgrade is safe) -> `release-diff`; published advisories for exact package versions (collection only; never says a version is safe) -> `advisory-collector`

Splits cleanly into independent parts (per module, per file group)? Run one Haiku agent per part in parallel and synthesise yourself.

Do NOT delegate (keep on the main model): debugging, root-cause analysis, architecture/design decisions, security or GxP/Part 11 judgement, validation conclusions, anything that edits files, anything needing exact line numbers for an edit.

Rules: give the subagent one precise question plus absolute paths; ask for terse bullets with path:line; treat its output as unverified, spot-check totals and counts, and re-read the cited lines yourself (or use `compliance-lister` with `Task kind: citation-verifier`) before acting on or editing from them. Category labels and "looks like placeholder" flags are heuristics for a human to confirm.
