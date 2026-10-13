# Cost policy: delegate cheap work to Haiku 5.5

Haiku 5.5 is ~20x cheaper than Sonnet 5.5 and ~40x cheaper than Opus 5.5 (at prompts up to 100k tokens; still cheaper above). Before doing a task yourself, ask: is it read-heavy, bounded and low-risk? If yes, delegate it with the Agent tool.

Delegate (Agent tool with `subagent_type` = one of the agents below (the plugin prefix is optional), or `model: "haiku"` on any other subagent call):
- Reading/summarising large or many files, logs, docs, specs -> `bulk-reader`; "where is X defined / used" -> `repo-scout`
- Package structure, import edges, file/module summaries -> `module-mapper`; dependency manifests (pyproject, package.json, requirements) -> `dependency-reader`
- Inventories (endpoints, config keys, dependencies, TODOs) -> `inventory-extractor`; requirements/IDs from specs and SOPs -> `spec-extractor`
- Web and documentation research (any depth, multiple sources) -> `doc-researcher`
- A page that must be opened in the browser (JS-rendered content, console errors, failed network requests, multi-page navigation) -> `browser-explorer` (read-only); named click/fill steps on a named page (it stops before submit, delete, send, pay, approve, export) -> `browser-operator`. The main thread cannot call the browser tools itself (a hook redirects it). One browser agent at a time; never for logins or irreversible actions. When a browser agent stops at a guard block, ask the user before doing that step yourself; never drive the browser around the guard
- Logs -> `log-triage`; pytest/jest/CI output -> `test-run-summarizer`; test inventory -> `test-case-lister`
- Alembic/migration chain structure (heads, branches, gaps) -> `migration-checker`
- Config key drift between .env.example / compose / settings -> `config-drift-checker` (never real .env files)
- Broken relative links in Markdown docs -> `doc-link-checker`; frontend calls vs backend routes -> `api-contract-checker`
- Which use cases reference the audit log (evidence only) -> `audit-coverage-lister`
- Hardcoded-credential candidates for human review (never prints values) -> `secret-candidate-lister`
- First-pass ticket triage (number, title, status, category) -> `ticket-classifier`
- First drafts of docs/docstrings/SOP outlines (reviewed before use) -> `doc-drafter`
- Checking another agent's `path:line` claims before you rely on them -> `citation-verifier`
- DB schema from DDL/migrations/ORM models -> `schema-reader`; OpenAPI/GraphQL contract -> `contract-reader`; CI/CD, Dockerfile, compose, Jenkinsfile description (secret names only, never values) -> `pipeline-reader`
- Changelog between two versions (breaking/deprecated entries, quoted with URL; never says an upgrade is safe) -> `release-diff`; published advisories for exact package versions (collection only; never says a version is safe) -> `advisory-collector`

Splits cleanly into independent parts (per module, per file group)? Run one Haiku agent per part in parallel and synthesise yourself.

Do NOT delegate (keep on the main model): debugging, root-cause analysis, architecture/design decisions, security or GxP/Part 11 judgement, validation conclusions, anything that edits files, anything needing exact line numbers for an edit.

Rules: give the subagent one precise question plus absolute paths; ask for terse bullets with path:line; treat its output as unverified, spot-check totals and counts, and re-read the cited lines yourself (or use `citation-verifier`) before acting on or editing from them. Category labels and "looks like placeholder" flags are heuristics for a human to confirm.
