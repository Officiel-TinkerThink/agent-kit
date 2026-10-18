# SUBAGENTS.md

Which subagents exist, what each one is for, and when the main agent should hand work to it.

**How to use this file.** Run `/haiku-delegation:subagents-init` in a project: it copies this file to the project root, imports it from `CLAUDE.md` (or `AGENTS.md`) with `@SUBAGENTS.md`, and adds the orchestrator rules (a marked block) to that same file. By hand: copy it and add that import line. Then add a "Project facts" section at the bottom (layout, exclusions). The four `agent-kit` plugins already inject a short delegation policy at session start; this file is the project-visible roster that makes the choice concrete. Always call an agent by its full name `<plugin>:<agent>` (for example `haiku-delegation:code-explorer`, `verification-runner:verification-runner`): a bare name such as `code-explorer` fails with "Agent type not found". The tables below use short names for readability; add the plugin prefix when you call the Agent tool (`haiku-delegation:` for `code-explorer`, `contracts-reader`, `infra-reader`, `docs-reader`, `triage`, `compliance-lister`, `researcher`, `browser-explorer` and `browser-operator`; `agent-guards:changelog-summarizer`; `agent-eval:annotator`; `code-review:` for `spec-reviewer`, `defect-reviewer`, `architecture-reviewer`, `security-reviewer`, `guidance-reviewer`, `history-reviewer`, `simplicity-reviewer` and `finding-validator`).

## Stance

Your context is the scarce resource. A subagent returns facts with `path:line` in 20-40 lines at about one twentieth of the cost per token; reading inline leaves the raw dump in your context for the rest of the session.

- **Handoff is the default; inline needs a reason.** Hand the reading off first, then keep working on the next independent step while the agent runs. Never sit waiting when there is independent work left.
- **A unit of work is the smallest piece of work that cannot be split any further**, whether the pieces could run in parallel or one after another: one question or one deliverable with one result. One agent per unit. A brief with a numbered list of steps, "and then", or several deliverables (read + write + test + document) holds several units; split it, and never hand a whole feature to one agent. Haiku input costs about 5x more once a single prompt passes 100k tokens, so a unit must be small enough to finish far below that. Wrong: one agent, brief "1. read prompt.py 2. write a loader 3. change the precedence 4. add tests 5. update the docs 6. run the tests". Right: in one message three read agents (where the cost is computed; the pricing fields; how other code opens a DB session), you write the loader, then in one message a docs draft and one test run. When you start a subagent other than a kit agent, always pass `model: "haiku"` and use the full `<plugin>:<agent>` name.
- **Fan out.** Independent units (per module, per file group, per question, per verification gate) go to one agent each, launched in a single message; dependent units go one after the other as each result arrives.
- **Agents return evidence, not judgement.** Counts reconciled, quotes verbatim, `NOT FOUND` / `UNCLEAR` marked, and no verdicts on safety, compliance or design. Judgement stays with you.
- **Treat every result as unverified.** Check totals, and run `compliance-lister` (`Task kind: citation-verifier`) on the `path:line` claims you will edit from.

## One agent per topic: say which kind of task

A topic agent replaces several narrower agents (12 agents in all). Each kind of task is one section of the agent with its own rules, output format and "will not" list; kinds named after an old agent (`log-triage`, `secret-candidate-lister`, ...) keep that agent's rules word for word. **The first line of your brief names the kind** (`Task kind: <kind>`), then the question follows. Name several kinds, separated by commas, when a task mixes them (`Task kind: locate, inventory`).

| Agent | Kinds | Default effort |
|---|---|---|
| `code-explorer` | `locate`, `read`, `map`, `inventory`, `tests` | low; `effort: medium` for `map` |
| `contracts-reader` | `schema`, `api-spec`, `migrations`, `api-match` | medium |
| `infra-reader` | `pipeline-reader`, `dependency-reader`, `config-drift-checker` | low; `effort: high` for `pipeline-reader`, `medium` for `config-drift-checker` |
| `docs-reader` | `spec-extractor`, `doc-link-checker`, `doc-drafter` | low; `effort: medium` for `spec-extractor` and `doc-drafter` |
| `triage` | `log-triage`, `test-run-summarizer`, `ticket-classifier` | low; `effort: medium` for `ticket-classifier` |
| `compliance-lister` | `audit-coverage-lister`, `secret-candidate-lister`, `citation-verifier` | low; `effort: medium` for `audit-coverage-lister`, `high` for the other two |
| `researcher` | `doc-researcher`, `release-diff`, `advisory-collector` | low; `effort: medium` for `doc-researcher`, `high` for `release-diff`, `max` for `advisory-collector` |
| `general-purpose` | none: a multi-step worker that delegates to the kit agents in parallel and asynchronously; an Agent call from the main agent with no `subagent_type`, or with `general-purpose`, is routed to it, and a subagent may not call `general-purpose` at all | medium |

The effort of each kind is the one its old agent ran at, listed in `kinds.txt` (a plugin file). The Agent tool's `effort` parameter sets it for one call.

A hook (`guard-task-kind`) blocks a brief that has no valid kind line and tells you what to add; re-issue the call with the line and nothing else changes. Without the line the agent would have to guess the section, and the usage log could not pick the right footer checks (Coverage, Reconciliation). Adding a topic later means a new row set in `kinds.txt` and a section in the agent, not a new agent.

## Before every Read, Grep, Glob, Bash or web call, check this table

If the action you are about to take matches a row, call the Agent tool instead. "Brief must carry" is what the agent needs from you: it sees nothing else, not this file and not the conversation.

### Find and read

Rows name the agent and the kind to put on the first line of the brief (see "One agent per topic" above).

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Read a file over about 80 lines, open a second file in one investigation, or run `cat`/`head`/`ls`/`grep` for facts you only need summarised | `code-explorer` | First line `Task kind: read`, then the exact question and the files; at most about 10 files per agent (it has a turn cap), split the rest | Speculate on bugs, design or compliance; edit anything |
| Search for anything beyond one known symbol in one known file | `code-explorer` | First line `Task kind: locate`, then the symbol, config key or endpoint, and the directory; say "whole word" if you need it | Map the whole repo; judge quality |
| List every endpoint, config key, env var, TODO, error message, requirement ID | `code-explorer` | First line `Task kind: inventory`, then the item kind and the glob | Infer items that are not written down (ambiguous ones are `UNCLEAR`) |
| Open a long log, stack trace or CI output | `triage` (`Task kind: log-triage`) | The file path | Diagnose root cause or suggest fixes |
| Open a saved pytest/jest/CI output file | `triage` (`Task kind: test-run-summarizer`) | The file path. (For a fresh run use `verification-runner`; it already summarises.) | Diagnose; assume a missing count is zero |

### Describe code and structure

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Map packages, import edges, layering, entry points or a module's public API | `code-explorer` | First line `Task kind: map`, then the target package(s); static versus dynamic imports if it matters | Judge the design |
| Read database DDL, migrations or ORM models for tables, columns, keys, indexes | `contracts-reader` | First line `Task kind: schema`, then the files; say whether you want per-statement history or the net schema | Normalise a type, suggest indexes, read seed or data rows |
| Inspect an Alembic (or similar) migrations directory: heads, branches, gaps, duplicate ids | `contracts-reader` | First line `Task kind: migrations`, then the migrations directory | Judge migration content or say what will fail |
| Compare frontend calls with backend routes | `contracts-reader` | First line `Task kind: api-match`, then both source roots, the router prefix, and the base URL the frontend uses | Predict runtime behaviour |
| Read an OpenAPI/Swagger or GraphQL schema | `contracts-reader` | First line `Task kind: api-spec`, then the schema file | Review the design or check an implementation |
| Find which use cases reference the audit log | `compliance-lister` (`Task kind: audit-coverage-lister`) | The glob of use-case files; optional search term (default `audit`) | Decide whether a NO is a defect or a YES is sufficient (that is a human GxP call) |
| Map tests to code, or find untested public symbols | `code-explorer` | First line `Task kind: tests`, then the test directory and source directory | Write tests; it is a name-reference check, not coverage |

### Describe configuration, infrastructure and dependencies

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Read `Jenkinsfile`, `Dockerfile`, compose files, GitHub Actions or other CI files | `infra-reader` (`Task kind: pipeline-reader`) | The file paths | Print secret values (names only); say the pipeline is good or safe |
| Compare config keys across `.env.example`, compose files and a settings class | `infra-reader` (`Task kind: config-drift-checker`) | Named files only; list the real `.env*` files and `*.bak` as exclusions | Open real `.env` files; say which source is right |
| Read dependency manifests (`pyproject.toml`, `package.json`, `pom.xml`, `go.mod`, Dockerfile base images) | `infra-reader` (`Task kind: dependency-reader`) | The manifest paths; ask for lockfile-resolved versions explicitly, it skips them otherwise | Assess security, licences or upgrade needs |
| Look up CVEs and advisories for pinned versions | `researcher` (`Task kind: advisory-collector`) | Exact `package@version` pairs | Say a version is "safe" or judge exploitability |
| Read a changelog between two versions | `researcher` (`Task kind: release-diff`) | The package and versions A and B | Conclude that an upgrade is safe; substitute nearby versions |
| Scan a directory for hardcoded-credential candidates | `compliance-lister` (`Task kind: secret-candidate-lister`) | One source directory (never the repo root) | Print any part of a value; say a candidate is or is not real |

### Specs, tickets and documents

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Pull requirements, IDs and acceptance criteria out of specs, SOPs, URS/FS, Jira exports or meeting notes | `docs-reader` (`Task kind: spec-extractor`) | The documents | Merge, reword, renumber or invent IDs (no ID means `(none)`); a human reviews before validation use |
| Triage a folder of ticket Markdown files | `triage` (`Task kind: ticket-classifier`) | **The category list** (for example defect / feature / refactor / docs-or-ops / other) | Invent categories (it uses `OTHER` or `UNCLEAR`); it is first-pass triage |
| Check Markdown for broken relative links | `docs-reader` (`Task kind: doc-link-checker`) | The document root | Edit files |
| Draft a docstring, README section, SOP outline or test description | `docs-reader` (`Task kind: doc-drafter`) | The source files; an example to match the format if you have one | Invent versions, IDs, dates or citations. Output starts `DRAFT - UNREVIEWED` and every `[VERIFY]` is yours to resolve before you write the file |

### Web research

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Any other web search or fetch: vendor docs, API references, standards and guidance lookups, release notes, how-to questions | `researcher` (`Task kind: doc-researcher`) | One clear question and the primary sources to prefer | Give compliance, validation or architecture recommendations; cite a URL it did not open |

### Browser (needs Claude in Chrome connected)

The main thread cannot call the browser tools itself; a hook redirects it to these two agents. Run one browser agent at a time (they share one browser).

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Open a page to read it: JS-rendered content, console errors, failed network requests, multi-page navigation, content inside iframes (it falls back to a screenshot and says so) | `browser-explorer` | The URL(s) and the exact question; local or approved hosts only | Click, type, submit or run scripts (a hook enforces read-only) |
| Click or fill named controls on a named page | `browser-operator` | The page, each control by its visible label, and what to report | Press anything the task did not name; submit, delete, send, pay, approve, sign, export or confirm (a hook blocks these and keeps an audit trail); type credentials |

If a browser agent stops at a guard block, **ask the user** before doing that step another way. Never drive the browser around the guard. The user can allow a blocked host with `/agent-guards:kit-allow`.

### Code review

One agent per focus, run in parallel, then one `finding-validator` per finding; only validated findings are reported. `/code-review:review <target> [spec path]` does all of this. Reviewers return candidates with a quoted code line and a concrete scenario; the validator returns CONFIRMED, REFUTED or UNVERIFIABLE. Whether a finding is acceptable stays with you and the human owner.

| About to... | Agent | Brief must carry | It will not |
|---|---|---|---|
| Check code against a written spec, issue or acceptance criteria | `spec-reviewer` | The spec path, the code or diff paths, one intent line | Review security or design the spec did not ask for; edit anything |
| Look for behavioural defects on a reachable path (wrong results, boundary and empty-value errors, unit confusion, swallowed exceptions, non-idempotent retries, missing transaction boundary, check-then-act races, resources not released) | `defect-reviewer` | One intent line, the code or diff paths | Report style, naming, structure with no failing path, or missing tests; judge compliance |
| Look for structure that breaks a documented dependency rule or forces a named change (layer direction, core importing adapters, concrete dependencies built in logic, leaky abstractions, duplicated rules, cycles, speculative generality) | `architecture-reviewer` | One intent line, the rule source path, the code or diff paths | Report runtime defects, style or missing tests; judge compliance; invent layers the repo does not define |
| Look for vulnerabilities in changed code (injection, access control, path traversal, SSRF, credentials, crypto, deserialization, audit trail) | `security-reviewer` | One intent line, the code or diff paths | Print credential values or write exploits; say code is safe |
| Check a change against CLAUDE.md, CONTRIBUTING, standards and guidance comments in the code | `guidance-reviewer` | The rule file paths, the code or diff paths | Report a rule that is silenced, out of scope or only a wish |
| Find regressions that only the history shows | `history-reviewer` | A history digest (commits with hunks, earlier PR comments), the change and the code | Run git itself; guess what the history says |
| Find logic the change added that a simpler form replaces with identical behaviour (boolean ladders, no-op try/except, one-implementation abstractions, flags every caller sets the same way, copied validators, needless caches) | `simplicity-reviewer` | One intent line, the code or diff paths | Report style, naming or bugs; propose a form that changes behaviour |
| Check one review finding before you act on it | `finding-validator` | One finding verbatim, the file paths to read, the spec or rule path if the finding has one | Add findings; confirm on an incomplete search |

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
| Before you edit based on another agent's `path:line` claims | `compliance-lister` (`Task kind: citation-verifier`) | The list of claims, each with file, line and the claimed text. Returns `CONFIRMED`, `WRONG LINE`, `WRONG TEXT` or `FILE MISSING` per claim |
| An agent's result turned out wrong, partial, non-compliant or missing something, and you verified that yourself | `annotator` | The agent id (or `last:<agent_type>`), what was wrong, what you expected, how you found out. Once per failed run; fix the task first. Never annotate style preferences or runs you did not check |

## Standing handoffs: no trigger needed from the user

- **After every batch of code edits:** `verification-runner`, once per gate (tests, lint, types, build), in parallel.
- **Before editing from an agent's result:** `compliance-lister` (`Task kind: citation-verifier`) on the claims you will rely on.
- **Dependency question:** `infra-reader` (`Task kind: dependency-reader`) first, then `researcher` (`Task kind: advisory-collector`) and `researcher` (`Task kind: release-diff`) in parallel on the versions it returned.
- **Task touched documents:** `docs-reader` (`Task kind: doc-link-checker`). **Task touched audit-relevant code:** `compliance-lister` (`Task kind: audit-coverage-lister`).
- **Agent result wrong or partial (you verified it):** fix the task, then `annotator` once, without being asked. See "Report agent failures to the annotator" below.

## Report agent failures to the annotator: on your own initiative

The user should never have to say "annotate that". When you find that a subagent's result is off, record it yourself. This is a standing duty, like running `verification-runner` after edits.

**Trigger: you verified it yourself** (a re-read of the cited lines, `compliance-lister` (`Task kind: citation-verifier`), a recount, a failing check, or the user pointing it out), and the run:

- stated a fact that is false, or a `path:line` that does not hold;
- gave a wrong count or total, or left out items that were in scope (`partial` or `missed`);
- broke a rule of its own definition or the format you asked for (a verdict where only evidence was allowed, scope creep, a write or command it should not have made);
- exposed a secret or personal data (describe by location and kind only, never the value);
- ended without a usable answer (`BLOCKED`, empty hand-back, a `no_final_answer` flag in the usage log) for a reason that points at the agent's instructions or the kit, not at your brief.

**Do it in this order:**

1. Fix the task first: redo the read, correct the count, or repeat the run with a better brief.
2. Call `annotator` once per failed run, in the background, and keep working. Give it: the agent id (or `last:<agent_type>`), what was wrong, what you expected, and how you found out; for `code-explorer` and `contracts-reader` also the `Task kind` of that run, so the failure can be attributed to the right section.
3. State only what you verified. A claim it cannot confirm is recorded as `disputed`, which counts against the record.
4. Mention it in the close-out line (`Annotated: <agent_type> <outcome>`).

**Do not annotate:** style or wording preferences, runs you did not check, a failure caused by a vague or wrong brief of your own (fix the brief), the same run twice, or an agent that correctly reported `NOT FOUND` or `UNCLEAR`. Never put secret values in the details.

## What stays on the main thread

Every edit, debugging and root cause, architecture and layering, security and authorization changes, GxP and 21 CFR Part 11 conclusions, validation conclusions, and upgrade-safety calls. Agents supply the evidence; you make the call.

Documents your project says to read before a change are decision inputs. Locate the section with `code-explorer` (`Task kind: locate`), then read that section yourself with an offset and limit.

## Writing a brief

An agent never sees `CLAUDE.md`, this file or the conversation. Each brief is self-contained:

0. **For `code-explorer` and `contracts-reader`: the first line is `Task kind: <kind>`.** A hook blocks the call without it.
1. **One precise question: one unit of work.** Not "look at the auth code", and not a numbered list of steps (each step is its own agent).
2. **Absolute paths** and the repository layout facts it needs (which folders exist, which are stale).
3. **The special input** from the tables above: category list, two refs, `package@version` pairs, the one command to run.
4. **The output you want:** terse bullets or a table, with `path:line`.
5. **Exclusions:** real `.env*` files, caches, build output, anything that holds secrets.

## Health and approvals

- `/agent-guards:kit-doctor` checks that the data folder is writable, the policy files are valid, hook errors, pending blocked hosts, and that the running plugin versions are the installed ones. Run it after an update or when records seem missing.
- `guard-task-kind` (a hook of `haiku-delegation`) blocks briefs for the topic agents that lack a valid `Task kind:` first line. The user can switch it off for a session by setting `TASK_KIND_GUARD=off`; it never blocks other agents and it fails open if it cannot read its input.
- `guard-agent-model` (a hook of `haiku-delegation`) blocks a call of a non-kit subagent (general-purpose, Explore, Plan, no type) that lacks `model: "haiku"`, and a brief for such an agent with 4 or more numbered steps or over 4000 characters (several units of work). Kit agents are never blocked. The user can switch the two checks off with `AGENT_MODEL_GUARD=off` and `AGENT_BRIEF_GUARD=off`. For the main agent, a call with no `subagent_type` or with `general-purpose` is routed to `haiku-delegation:general-purpose`; for a subagent, a call of `general-purpose` or with no type is blocked (`AGENT_GENERAL_ROUTE=off` lifts both). It fails open if it cannot read its input.
- `/agent-guards:kit-allow` (only the user can start it) records the user's approval of a blocked browser host in `browser-policy.json`, with a reason and file hashes in `audit/policy-changes.jsonl`.

## Close-out

End every task with one line: `Handoffs: <agent x count>` or `Inline: <reason>`. Reading three or more files inline with no handoff needs a stated reason. If a delegated result failed your check, add `Annotated: <agent_type> <outcome>`, or `Annotate: skipped, <reason>`.

## Project facts (fill in per project)

- Repository layout and which folders are stale or generated:
- Files and folders agents must never read (beyond `.env*`):
- The one command per verification gate (tests, lint, types, build):
- Where the specs, SOPs and decision records live:
