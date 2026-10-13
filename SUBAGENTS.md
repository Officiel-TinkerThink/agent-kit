# SUBAGENTS.md

Which subagents exist, what each one is for, and when the main agent should hand work to it.

**How to use this file.** Copy it into a project and import it from `CLAUDE.md` (or `AGENTS.md`) with `@SUBAGENTS.md`. Add a "Project facts" section at the bottom (layout, exclusions). The four `agent-kit` plugins already inject a short delegation policy at session start; this file is the project-visible roster that makes the choice concrete. Agents are addressed as `<plugin>:<agent>` (for example `haiku-delegation:bulk-reader`); the plain name also works.

## Stance

Your context is the scarce resource. A subagent returns facts with `path:line` in 20-40 lines at about one twentieth of the cost per token; reading inline leaves the raw dump in your context for the rest of the session.

- **Handoff is the default; inline needs a reason.** Hand the reading off first, then keep working on the next independent step while the agent runs. Never sit waiting when there is independent work left.
- **Fan out.** Independent parts (per module, per file group, per question, per verification gate) go to one agent each, launched in a single message.
- **Agents return evidence, not judgement.** Counts reconciled, quotes verbatim, `NOT FOUND` / `UNCLEAR` marked, and no verdicts on safety, compliance or design. Judgement stays with you.
- **Treat every result as unverified.** Check totals, and run `citation-verifier` on the `path:line` claims you will edit from.

## Before every Read, Grep, Glob, Bash or web call, check this table

If the action you are about to take matches a row, call the Agent tool instead. "Brief must carry" is what the agent needs from you: it sees nothing else, not this file and not the conversation.

### Find and read

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Read a file over about 80 lines, open a second file in one investigation, or run `cat`/`head`/`ls`/`grep` for facts you only need summarised | `bulk-reader` | The exact question and the files; at most about 10 files per agent (it has a turn cap), split the rest | Speculate on bugs, design or compliance; edit anything |
| Search for anything beyond one known symbol in one known file | `repo-scout` | The symbol, config key or endpoint, and the directory; say "whole word" if you need it | Map the whole repo; judge quality |
| List every endpoint, config key, env var, TODO, error message, requirement ID | `inventory-extractor` | The item kind and the glob | Infer items that are not written down (ambiguous ones are `UNCLEAR`) |
| Open a long log, stack trace or CI output | `log-triage` | The file path | Diagnose root cause or suggest fixes |
| Open a saved pytest/jest/CI output file | `test-run-summarizer` | The file path. (For a fresh run use `verification-runner`; it already summarises.) | Diagnose; assume a missing count is zero |

### Describe code and structure

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Map packages, import edges, layering, entry points or a module's public API | `module-mapper` | The target package(s); static versus dynamic imports if it matters | Judge the design |
| Read database DDL, migrations or ORM models for tables, columns, keys, indexes | `schema-reader` | The files; say whether you want per-statement history or the net schema | Normalise a type, suggest indexes, read seed or data rows |
| Inspect an Alembic (or similar) migrations directory: heads, branches, gaps, duplicate ids | `migration-checker` | The migrations directory | Judge migration content or say what will fail |
| Compare frontend calls with backend routes | `api-contract-checker` | Both source roots, the router prefix, and the base URL the frontend uses | Predict runtime behaviour |
| Read an OpenAPI/Swagger or GraphQL schema | `contract-reader` | The schema file | Review the design or check an implementation |
| Find which use cases reference the audit log | `audit-coverage-lister` | The glob of use-case files; optional search term (default `audit`) | Decide whether a NO is a defect or a YES is sufficient (that is a human GxP call) |
| Map tests to code, or find untested public symbols | `test-case-lister` | Test directory and source directory | Write tests; it is a name-reference check, not coverage |

### Describe configuration, infrastructure and dependencies

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Read `Jenkinsfile`, `Dockerfile`, compose files, GitHub Actions or other CI files | `pipeline-reader` | The file paths | Print secret values (names only); say the pipeline is good or safe |
| Compare config keys across `.env.example`, compose files and a settings class | `config-drift-checker` | Named files only; list the real `.env*` files and `*.bak` as exclusions | Open real `.env` files; say which source is right |
| Read dependency manifests (`pyproject.toml`, `package.json`, `pom.xml`, `go.mod`, Dockerfile base images) | `dependency-reader` | The manifest paths; ask for lockfile-resolved versions explicitly, it skips them otherwise | Assess security, licences or upgrade needs |
| Look up CVEs and advisories for pinned versions | `advisory-collector` | Exact `package@version` pairs | Say a version is "safe" or judge exploitability |
| Read a changelog between two versions | `release-diff` | The package and versions A and B | Conclude that an upgrade is safe; substitute nearby versions |
| Scan a directory for hardcoded-credential candidates | `secret-candidate-lister` | One source directory (never the repo root) | Print any part of a value; say a candidate is or is not real |

### Specs, tickets and documents

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Pull requirements, IDs and acceptance criteria out of specs, SOPs, URS/FS, Jira exports or meeting notes | `spec-extractor` | The documents | Merge, reword, renumber or invent IDs (no ID means `(none)`); a human reviews before validation use |
| Triage a folder of ticket Markdown files | `ticket-classifier` | **The category list** (for example defect / feature / refactor / docs-or-ops / other) | Invent categories (it uses `OTHER` or `UNCLEAR`); it is first-pass triage |
| Check Markdown for broken relative links | `doc-link-checker` | The document root | Edit files |
| Draft a docstring, README section, SOP outline or test description | `doc-drafter` | The source files; an example to match the format if you have one | Invent versions, IDs, dates or citations. Output starts `DRAFT - UNREVIEWED` and every `[VERIFY]` is yours to resolve before you write the file |

### Web research

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Any other web search or fetch: vendor docs, API references, standards and guidance lookups, release notes, how-to questions | `doc-researcher` | One clear question and the primary sources to prefer | Give compliance, validation or architecture recommendations; cite a URL it did not open |

### Browser (needs Claude in Chrome connected)

The main thread cannot call the browser tools itself; a hook redirects it to these two agents. Run one browser agent at a time (they share one browser).

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Open a page to read it: JS-rendered content, console errors, failed network requests, multi-page navigation, content inside iframes (it falls back to a screenshot and says so) | `browser-explorer` | The URL(s) and the exact question; local or approved hosts only | Click, type, submit or run scripts (a hook enforces read-only) |
| Click or fill named controls on a named page | `browser-operator` | The page, each control by its visible label, and what to report | Press anything the task did not name; submit, delete, send, pay, approve, sign, export or confirm (a hook blocks these and keeps an audit trail); type credentials |

If a browser agent stops at a guard block, **ask the user** before doing that step another way. Never drive the browser around the guard. The user can allow a blocked host with `/agent-guards:kit-allow`.

### Run and verify

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Run tests, a linter, a type check or a build | `verification-runner` | Exactly one command per agent, taken from the project's README; one agent per gate so they run in parallel | Install, edit or try another command if one is refused. Output goes to its own log; you get the verdict, the first failures and the log path |
| Delete files or folders (only on request) | `verification-runner` | Absolute paths | Delete for real: an `rm` becomes a move to a restorable quarantine inside configured zones |

Which commands the runner may run is decided by **Claude Code's own permissions** (your allow, ask and deny rules and the permission mode). If it reports that a command was refused or needs permission, do not run that command yourself around it: ask the user whether to allow it, and re-run only after their answer. It runs the project's own code, so use it on trusted repositories only.

### Git

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Summarise history or a diff: what changed between two refs, grouped by area | `changelog-summarizer` | Two refs, and which repository if the project has more than one | Run anything but a single read-only git command; judge correctness |

### Keeping the agents honest

| When | Agent | Brief must carry |
|---|---|---|
| Before you edit based on another agent's `path:line` claims | `citation-verifier` | The list of claims, each with file, line and the claimed text. Returns `CONFIRMED`, `WRONG LINE`, `WRONG TEXT` or `FILE MISSING` per claim |
| An agent's result turned out wrong, partial, non-compliant or missing something, and you verified that yourself | `annotator` | The agent id (or `last:<agent_type>`), what was wrong, what you expected, how you found out. Once per failed run; fix the task first. Never annotate style preferences or runs you did not check |

## Standing handoffs: no trigger needed from the user

- **After every batch of code edits:** `verification-runner`, once per gate (tests, lint, types, build), in parallel.
- **Before editing from an agent's result:** `citation-verifier` on the claims you will rely on.
- **Dependency question:** `dependency-reader` first, then `advisory-collector` and `release-diff` in parallel on the versions it returned.
- **Task touched documents:** `doc-link-checker`. **Task touched audit-relevant code:** `audit-coverage-lister`.
- **Agent result wrong or partial:** fix the task, then `annotator` once.

## What stays on the main thread

Every edit, debugging and root cause, architecture and layering, security and authorization changes, GxP and 21 CFR Part 11 conclusions, validation conclusions, and upgrade-safety calls. Agents supply the evidence; you make the call.

Documents your project says to read before a change are decision inputs. Locate the section with `repo-scout`, then read that section yourself with an offset and limit.

## Writing a brief

An agent never sees `CLAUDE.md`, this file or the conversation. Each brief is self-contained:

1. **One precise question.** Not "look at the auth code".
2. **Absolute paths** and the repository layout facts it needs (which folders exist, which are stale).
3. **The special input** from the tables above: category list, two refs, `package@version` pairs, the one command to run.
4. **The output you want:** terse bullets or a table, with `path:line`.
5. **Exclusions:** real `.env*` files, caches, build output, anything that holds secrets.

## Health and approvals

- `/agent-guards:kit-doctor` checks that the data folder is writable, the policy files are valid, hook errors, pending blocked hosts, and that the running plugin versions are the installed ones. Run it after an update or when records seem missing.
- `/agent-guards:kit-allow` (only the user can start it) records the user's approval of a blocked browser host in `browser-policy.json`, with a reason and file hashes in `audit/policy-changes.jsonl`.

## Close-out

End every task with one line: `Handoffs: <agent x count>` or `Inline: <reason>`. Reading three or more files inline with no handoff needs a stated reason.

## Project facts (fill in per project)

- Repository layout and which folders are stale or generated:
- Files and folders agents must never read (beyond `.env*`):
- The one command per verification gate (tests, lint, types, build):
- Where the specs, SOPs and decision records live:
