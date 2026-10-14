# Changelog

All notable changes to agent-kit are recorded here, newest first. The four plugins (`haiku-delegation`, `agent-guards`, `agent-eval`, `verification-runner`) and the marketplace entry are released together under one version number. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/) while below 1.0 (a new feature bumps the patch number).

**How to keep it.** Each pull request adds its own line under `## [Unreleased]` and does not change any version; a separate release step renames `[Unreleased]` to the version and date and bumps the versions. The full rules, the release steps and the pull request template are in [`CONTRIBUTING.md`](CONTRIBUTING.md). `tests/haiku-delegation/test_changelog.py` checks that this file and the version numbers agree.

## [Unreleased]

### Fixed
- The secret guard (`agent-guards`, `guard-secret-leak`) no longer replaces TypeScript generic types with `<redacted:secret>`. A line such as `const SECRET_LABELS: Record<string, string> = {}` lost `Record<string` because the key contains `SECRET` and the key/value rule took the type as the value; a generic type (`Record<`, `Map<`, `Promise<`) is now never a value, and plural key names (`labels`, `names`, `types` ...) are excluded like their singular forms. Real passwords and tokens are still redacted. Both the PowerShell and the shell guard; the shell guard now has its own test (`tests/agent-guards/test_guard_secret_leak_sh.py`).
- A subagent the user stopped could not be annotated: it never reaches the `SubagentStop` hook, so `usage/agent-usage.jsonl` had no record of it and the `annotator` found 0 matches. A new `SubagentStart` hook in `agent-eval` (`subagent-start-log`, PowerShell and shell) now writes a small start record (ids, agent type, time, transcript path; no prompt or answer) to `usage/agent-starts.jsonl`. The `annotator` falls back to it when there is no usage record, notes in the summary that the run was unfinished, and `annotate.py` records `run_record: start-only`. Nothing that reads `agent-usage.jsonl` changes. (`tests/agent-eval/test_stopped_run.py`)
- The bulk-read redirect (`check-bulk-read`) wrongly implied that a chunked read (`offset`/`limit`) is only for edits or exact line numbers. The message now says chunked reads are always allowed, for any purpose including reviews, and that only whole-file reads over the limit are redirected; the block texts of `check-bulk-read` and `guard-env-files` also say they are an intentional guard, not a hook failure. Claude Code itself prefixes every hook block with "hook error"; the kit cannot change that label. (`tests/agent-guards/test_guard_messages.py`)
- `tests/linux/pwsh` (the Linux test shim) is now pinned to LF in `.gitattributes`; a Windows clone with `core.autocrlf=true` checked it out with CRLF and the container suite failed with `FileNotFoundError: 'pwsh'`.

## [0.1.14] - 2026-10-14

### Added
- `/haiku-delegation:subagents-init`: copies `SUBAGENTS.md` into the current project root and adds an `@SUBAGENTS.md` import to `CLAUDE.md` (or `AGENTS.md`, or a new `CLAUDE.md`). Safe to repeat: an identical file is `UNCHANGED`, the import is never added twice, and a `SUBAGENTS.md` the project edited is kept. Options: `update` (refresh the shipped part above "Project facts", keep the project's facts, write `SUBAGENTS.md.bak-<timestamp>`; running it twice changes nothing), `dry-run`, `claude` or `agents` to choose the import target, or a folder path. Shell and PowerShell versions behave identically. User-started only.
- `SUBAGENTS.md`: new section "Report agent failures to the annotator: on your own initiative". The main agent records a verified failure of a subagent (false fact, wrong count, omission, broken rule, exposed secret, no usable answer) without the user having to ask: fix the task first, then call `annotator` once per failed run, and note it in the close-out line. Lists what not to annotate (style preferences, unchecked runs, its own vague briefs, duplicates).
- `CONTRIBUTING.md` and a pull request template: the changelog line goes in the PR, versions are bumped only in a separate release step (rules, release steps and notes for agents).
- README: "Set up each project (once per project)" explains how to put the roster into a project; "Update and uninstall" now says what to do in each project after a kit update; this changelog.
- Tests: `test_subagents_init.py` (both tools, identical output, idempotence), `test_changelog.py`.

### Changed
- `SUBAGENTS.md`: the "Standing handoffs" bullet for wrong or partial agent results now says to annotate without being asked; the close-out line adds `Annotated: <agent_type> <outcome>` or `Annotate: skipped, <reason>`.
- A copy of `SUBAGENTS.md` now ships inside `plugins/haiku-delegation/templates/` (an installed plugin cannot read the repository root). A test fails if the two copies differ.

## [0.1.13] - 2026-10-14

### Fixed
- Ubuntu and other Linux machines with a UTF-8 locale (`en_US.UTF-8`, `C.UTF-8`) never wrote a usage record: gawk 5 rejected the byte-range patterns of the checks program, the hook logged `run record not written: output checks failed` for every run, `usage/agent-usage.jsonl` was never created and the `annotator` rejected every run id as unknown. `subagent-usage-log.sh` now forces `LC_ALL=C` for its awk stages. Windows was not affected.
- The awk error text, which was thrown away, is now part of the `hook-errors.log` line, so a failure of this kind cannot hide again.

### Added
- `tests/agent-eval/test_usage_log_sh_locale.py` runs the real hook under the `C` locale and every installed UTF-8 locale and requires a run record. Fails on 0.1.12 under `C.utf8`.

## [0.1.12] - 2026-10-13

### Changed
- Linux runs native POSIX `sh` scripts: no PowerShell and no Python needed. `scripts/run.sh` is the OS-neutral launcher (`powershell.exe` on the PATH runs `<script>.ps1`, otherwise `<script>.sh`). Hooks, skills and the safe-rm rewrite no longer name a shell language in any command shown to a user or an agent.

### Added
- A `.sh` twin for every hook and tool (guards, secret redaction, browser guard, bulk-read redirect, usage log, annotator guard, `kit-policy`, `kit-doctor`, safe-rm, runner guard, session context), built on a shared `lib.sh`. Needs only `sh`, `awk`, `sed`, `grep` and coreutils; verified under `dash` and `mawk`.
- Tests for `lib.sh`, the launcher and shell purity; the Linux test image has no PowerShell. 16 suites pass on Windows and on Ubuntu 24.04.

## [0.1.11] - 2026-10-13

### Added
- Ubuntu Linux support alongside Windows (via PowerShell 7 at this version; replaced by native `sh` in 0.1.12). Safe-rm and the runner guard handle POSIX paths; `tests/linux` runs the suite in an Ubuntu 24.04 container.
- `SUBAGENTS.md`: roster of all 29 subagents and when the main agent should hand work to them, with standing handoffs, brief rules, a close-out line and a "Project facts" section. A test checks that every shipped agent is listed and no unknown agent is named.

## [0.1.10] - 2026-10-13

### Added
- Initial release: four plugins. `haiku-delegation` (read-only Haiku 5.5 subagents with effort tiers and a delegation policy), `agent-guards` (secret redaction, `.env` protection, bulk-read redirect, monitor guard, browser guard, read-only git), `agent-eval` (usage log with deterministic contract checks, `annotator` agent, judge and review CLIs), `verification-runner` (test, lint and build runner with safe-rm quarantine).
