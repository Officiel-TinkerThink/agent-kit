# agent-kit

Claude Code plugins for cost-aware, auditable use of subagents in GxP-regulated engineering teams. Windows (PowerShell 5.1) and Ubuntu Linux (POSIX sh; nothing to install) (see "Platform").

| Plugin | What it gives you | Standalone? |
|---|---|---|
| `haiku-delegation` | 7 read-only Haiku 5.5 topic agents (code, contracts, infra, docs, triage, compliance, web research) each serving several kinds of task named on the first line of the brief, with per-kind effort tiers, two browser agents for Claude in Chrome (`browser-explorer` read-only, `browser-operator` for named steps), and a session policy telling the main model when to delegate | yes |
| `agent-guards` | Deterministic hooks: secret redaction at hand-back and web-exfiltration block, `.env` protection, bulk-read redirect, monitor/poll blocking, read-only git for `changelog-summarizer` | yes (best with `haiku-delegation`) |
| `agent-eval` | Per-run usage log with deterministic contract checks, an `annotator` agent for warm failure annotations, operator CLIs for judging and human review | yes (best with the others) |
| `verification-runner` | A Haiku agent that runs tests / linters / builds (Claude Code's permissions decide which commands) and reports only the verdict; deletes go through safe-rm (quarantine, audit, restore) | yes |

## Installation

### Before you start
- **Claude Code** (a recent version; `claude --version`). Nothing else is needed to run the plugins: on **Windows** the hooks are PowerShell 5.1 scripts (already installed), on **Ubuntu/Linux/macOS** they are POSIX `sh` scripts that use only `sh`, `awk`, `sed`, `grep` and coreutils. No PowerShell and no Python is installed or used on Linux.
- **Python 3.10+** only if you want to run the tests, the operator CLIs of `agent-eval`, or the browser benchmark.
- **Claude in Chrome** (the Chrome extension, connected to Claude Code) only if you want the two browser agents.
- **Hooks run code on your machine.** Read `plugins/*/scripts` and `plugins/*/hooks/hooks.json` before installing, install from a repository you trust, and pin a released version. Treat an installed version as a controlled software release in your QMS.

### Linux needs nothing extra
Every hook and skill is started through `scripts/run.sh`, which looks at the machine: with `powershell.exe` on the `PATH` (Windows) it runs `<script>.ps1`, otherwise it runs `<script>.sh` in POSIX `sh` (Ubuntu's `dash`, busybox, bash). No command shown to you or to an agent names a shell language. If a script has no version for the machine, the hook exits with code 2 and says so (a guard that cannot run blocks instead of silently doing nothing). Tested on Ubuntu 24.04 (`dash`, `mawk`) in a container that has no PowerShell and no Python.

### Install (from inside Claude Code)
```
/plugin marketplace add Officiel-TinkerThink/agent-kit
/plugin install haiku-delegation@agent-kit
/plugin install agent-guards@agent-kit
/plugin install agent-eval@agent-kit
/plugin install verification-runner@agent-kit
```
The same from a terminal:
```
claude plugin marketplace add Officiel-TinkerThink/agent-kit
claude plugin install haiku-delegation@agent-kit
claude plugin install agent-guards@agent-kit
claude plugin install agent-eval@agent-kit
claude plugin install verification-runner@agent-kit
```
You do not need all four. `haiku-delegation` is the core; `agent-guards` is strongly recommended with it (it holds the browser guard, secret redaction and the bulk-read redirect); `agent-eval` and `verification-runner` are optional. If the repository is private, Claude Code needs your Git credentials to read it (sign in to GitHub first, for example with Git Credential Manager).

### Check that it works
1. **Restart Claude Code.** New agents and hooks are loaded at session start.
2. Run `/agents`: you should see the `haiku-delegation` agents (for example `code-explorer`, `contracts-reader`, `browser-explorer`) with their descriptions.
3. Run `/agent-guards:kit-doctor`. Expect `0 FAIL`. A `WARN` on the first run is normal when no policy files exist yet; it tells you what each line means.
4. Ask for something a subagent should do, for example "find where `main` is defined in this repo", and watch the main agent delegate to `code-explorer`. The session policy that tells the main model when to delegate is injected automatically at session start by the plugin; you do not need to edit `CLAUDE.md` for that (for the per-project roster see the next section).

### Set up each project (once per project)
Installing the plugins is per machine; the project roster is per project. In every project where you want the main agent to delegate consistently, open Claude Code in that project and run:
```
/haiku-delegation:subagents-init
```
It copies [`SUBAGENTS.md`](SUBAGENTS.md) (which agent for which job, what each brief must carry, the standing handoffs, and the duty to report a failed agent run to the `annotator` without being asked) to the project root, adds an `@SUBAGENTS.md` import to `CLAUDE.md` (or `AGENTS.md` when that is the file the project has; a new `CLAUDE.md` if there is neither), and adds the shipped orchestrator rules (the plugin's `AGENTS.md` text) to that same file as a block between two marker lines. Everything already in the file is kept byte for byte, and the rules are never added twice (if the same text is already in the file it is left alone). Then fill in the "Project facts" section at the bottom of `SUBAGENTS.md`: layout and stale folders, files agents must never read, the one command per verification gate. Commit both files so the whole team gets them.

- **Safe to repeat.** Running it again changes nothing once everything is current: an identical `SUBAGENTS.md` is reported `UNCHANGED`, and the import and the rules block are never added twice (`ORCHESTRATION up to date`).
- **After a kit update** (new `SUBAGENTS.md` or rules text): run `/haiku-delegation:subagents-init` again. A `SUBAGENTS.md` that differs from the shipped one is refreshed: everything above "Project facts" becomes the shipped text, your own facts are kept, and `SUBAGENTS.md.bak-<timestamp>` is written first (a `SUBAGENTS.md` without a "Project facts" section is left alone with a note, to be merged by hand). An outdated rules block is refreshed the same way: only the text between the two marker lines changes, after writing `CLAUDE.md.bak-<timestamp>` (or `AGENTS.md.bak-...`). Edits you made above "Project facts" are replaced, so keep your own text below it (or in the backup). Running it twice is a no-op.
- **Options:** `keep` leaves an existing `SUBAGENTS.md` and rules block as they are (`EXISTS ... (-Keep)`, `ORCHESTRATION outdated`); `dry-run` shows what would happen and writes nothing; `claude` or `agents` forces the import target; `no-orchestration` skips the rules block; a folder path sets the project (default: the git top level of the current folder).
- **Claude Code version:** v2.1.277 or newer (see "Platform"). Older versions do not load an `AGENTS.md` on their own.
- **By hand:** copy the file and add the line `@SUBAGENTS.md` to `CLAUDE.md` yourself; copy the rules from `plugins/haiku-delegation/templates/AGENTS.md` if you want them. If you edit the root `SUBAGENTS.md` in this repository, copy it to `plugins/haiku-delegation/templates/SUBAGENTS.md` too; the same for the root `AGENTS.md` and `plugins/haiku-delegation/templates/AGENTS.md` (a test checks that each pair matches).
- The session policy injected by the plugins works without this step; the roster makes the choice concrete per project and is what makes the main agent report agent failures on its own.

### Optional setup
- **Browser agents:** install the Claude in Chrome extension and connect it to Claude Code. The main thread cannot call the browser tools itself; a hook redirects it to `browser-explorer` (read-only) or `browser-operator` (named click and fill steps, which stops before submit, delete, send, pay, approve and export). Details and benchmark results: `plugins/haiku-delegation/README.md`.
- **Which commands the test runner may run:** Claude Code's own permissions decide. Add allow rules for the commands you trust to your Claude Code settings (for example `Bash(pytest:*)` or `Bash(npm run test:*)`), or approve the prompt when it appears. The kit adds no command list of its own.
- **Where the kit keeps its data** (audit logs, usage records, policy files): see "Where data lives" below. Set `AGENT_KIT_DATA` to put it somewhere specific.

### Update and uninstall
```
claude plugin marketplace update agent-kit
claude plugin update haiku-delegation@agent-kit      # repeat for each plugin you installed
```
Restart Claude Code afterwards, then run `/agent-guards:kit-doctor` (it checks that the running version is the installed one). Claude Code updates a plugin only when its `version` changes, so a release is what delivers new agents, hooks and skills; see [`CHANGELOG.md`](CHANGELOG.md) for what each version contains. Projects that use the roster run `/haiku-delegation:subagents-init` once after an update to refresh `SUBAGENTS.md` and the rules block (your "Project facts" are kept and a backup is written). To remove a plugin: `claude plugin uninstall <plugin>@agent-kit`. The data folder is left in place so your audit records are kept; delete it yourself if you do not need them.

Plugin agents are addressed by their full name `<plugin>:<agent>` (for example `haiku-delegation:code-explorer`); a bare name such as `code-explorer` fails with "Agent type not found".

## Where data lives
All state is in one folder (KIT_DATA), resolved in this order by every hook and CLI: `$AGENT_KIT_DATA`; `<CLAUDE_CONFIG_DIR>/agent-kit`; the config folder the plugin is installed under (derived from the script's own `.../plugins/cache/...` path, so it still works when `CLAUDE_CONFIG_DIR` is not passed to the hook, e.g. `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`); `~/.claude/agent-kit`. The plugins' own `${CLAUDE_PLUGIN_DATA}` is not used: it is per plugin and deleted on uninstall, while the audit and usage data is shared by four plugins and must outlive any one of them.

When an audit or usage write fails, the hook appends the reason to `hook-errors.log` in that folder. The one fail-closed case: a `browser-operator` step is blocked when its audit record cannot be written (no record, no action). Other audit writes fail open and are traced, because the guard itself still enforces. Operator CLIs run from a terminal outside the plugin cache need `CLAUDE_CONFIG_DIR` or `AGENT_KIT_DATA` set to find the same folder.
```
usage/agent-usage.jsonl          one record per subagent run (agent-eval)
audit/secret-guard-audit.jsonl   redaction / block events: kinds and counts only, never values (agent-guards)
audit/bulk-read-audit.jsonl      blocked whole-file reads (agent-guards)
eval/                            annotations, judgements, reviews, inbox, calibration (agent-eval)
verification-logs/               full test output + _deletions.jsonl (verification-runner)
quarantine/                      what safe-rm moved instead of deleting
safe-rm-policy.json              YOUR zones where the runner may delete (optional; see below)
browser-policy.json              YOUR host allowlist for the browser agents (optional; /agent-guards:kit-allow adds hosts)
audit/blocked-requests.jsonl     browser hosts the guard blocked, waiting for the user's decision
audit/policy-changes.jsonl       every approved host change: who, when, why, SHA-256 of the file before and after
audit/browser-actions.jsonl      every browser-operator decision (typed text never stored)
hook-errors.log                  why a hook or audit write failed
reports/                         drafts of /agent-eval:report-issue, kept until you delete them (agent-eval)
```
Logs hold no prompts, answers or file content. Back this folder up if you need the records to endure.

## Configuration
- `BULK_READ_MIN_LINES` (environment variable, default 200): whole-file reads above this are redirected to `code-explorer`.
- **safe-rm zones:** by default the verification-runner can delete only one file at a time inside its own `verification-logs` folder. To let it clean build artefacts in your projects, copy `plugins/verification-runner/policy/safe-rm-policy.default.json` to `<data>/safe-rm-policy.json` and add entries to `allowedRoots` (`path`, `minDepth` below the root, `allowGlob`, `maxItems`). `${DATA}` expands to the data folder. Protected names (`.git`, `.env*`, keys, databases, ...) are always refused. Restore with `powershell -File <plugin>/scripts/safe-rm-restore.ps1 -List` / `-Id <id>`; purge by deleting folders under `quarantine/` yourself.
- **Effort tiers** (frontmatter `effort:` per agent): low = mechanical extraction; medium = multi-source reconciliation, classification, drafting; high = a silent miss or leak is costly; max = `advisory-collector`, `annotator`. These are judgement-based starting points, not benchmark-proven (accuracy did not differ between low and max on 8 tasks, n = 2 each; max cost 4-15x more). Tune them from the usage log.

## Approving what a guard blocked, and checking health
- **Which commands the verification-runner may run is decided by Claude Code's own permissions** (your allow, ask and deny rules, the permission mode and the prompts); the kit keeps no command list of its own. A command that is refused or needs permission is reported back by the runner, and the main agent asks you. The kit only adds what permission rules cannot express: deletes go through the safe-rm quarantine (a delete hidden inside another command is refused), and evidence logs are written as new files only.
- `/agent-guards:kit-allow` (user-invoked only): lists the browser hosts that the guard blocked (`audit/blocked-requests.jsonl`), asks you which to allow and why, then adds them to `browser-policy.json` through `kit-policy.ps1`. Each change is appended to `audit/policy-changes.jsonl` with the SHA-256 of the file before and after. The agents cannot run it or edit the file.
- `/agent-guards:kit-doctor`: read-only health check. It shows where KIT_DATA resolves and whether the candidates agree, whether each folder is writable, whether the policy files are valid, whether a policy file changed outside `/agent-guards:kit-allow` (hash against the last recorded change), hook errors from the last 24 hours, pending blocked requests, and installed versus running plugin versions (restart needed). Run it after an update or when records seem missing.
- Policy files are controlled documents: back up `<data>`, and review `audit/policy-changes.jsonl` as the change record.

## Operator routine (outside Claude sessions)
The scripts are inside the installed plugin (`<config dir>/plugins/cache/agent-kit/agent-eval/<version>/scripts/`).
```
python agent_eval.py status | queue | calibrate | judge --limit 10 | review | report | export
python agent-usage-report.py [--days N] [--agent NAME]
python agent-usage-note.py <agent_id|last> ok|corrected|missed "note"
```
The judge (a stronger model through `claude -p`, about $0.10 per case) and your review are never automatic. `calibrate` needs `<data>/eval/calibration.jsonl`: lines of `{"id", "agent_type", "prompt", "answer", "expected": "pass"|"fail", "defect"}` built from real outputs of your agents plus copies with one planted defect each; measure the judge before trusting it.

## What the guards cannot do
- Secret redaction covers subagent answers and subagent web calls. It does not cover the main model reading a secret directly, files a subagent writes, or re-encoded values (base64). Values with no recognisable shape that the agent never read as key=value, URL credential or CLI argument are not detected. Pure lowercase values of 9 characters or fewer are treated as words.
- A subagent that silently omits an item from a list leaves no trace; only sampling and human review find it.
- The `verification-runner` executes the project's own code: trusted repositories only.
- Guards refuse paths containing `~` (8.3 short names); keep the data folder on a normal long path.

## Platform
- **Claude Code: v2.1.277 or newer is the supported version.** From that version Claude Code reads a project's `AGENTS.md` itself when there is no `CLAUDE.md` and expands `@` imports inside it, which `/haiku-delegation:subagents-init` relies on when it writes the `@SUBAGENTS.md` import and the rules block into `AGENTS.md`. On an older Claude Code, a project that has only an `AGENTS.md` does not load it: add a `CLAUDE.md` containing `@AGENTS.md`, or upgrade. Check with `claude --version`.
- **Windows:** PowerShell 5.1 scripts (`*.ps1`). **Ubuntu/Linux:** POSIX `sh` scripts (`*.sh`, same behaviour, same flags, same data files) chosen automatically by `scripts/run.sh`. Paths are handled per platform (on Linux: absolute `/` paths, case-sensitive, no drive letters; `safe-rm` zones in `safe-rm-policy.json` must be `/` paths on Linux, entries written as `D:/...` are ignored there). macOS should behave like Linux but is not tested.
- The agents and policies are platform-independent. The optional Python tools (`agent_eval.py`, usage reports, the benchmark) need Python 3 on any platform; the hooks do not.
- Hooks start through `sh scripts/run.sh`; on Windows this needs Git Bash, which Claude Code on Windows already requires. Linux needs only the `sh`, `awk`, `sed`, `grep` and coreutils that ship with Ubuntu.
- Project-specific commands in `verification-runner` use the platform's own layout (for example `.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on Linux).

## About the secret-looking strings in tests
The files under `tests/` contain deliberately fake credentials (AWS-, GitHub-, Slack- and Sonar-shaped tokens, a PEM header, test passwords) used to prove that redaction works. They are fixtures, not secrets; if your organisation runs a secret scanner on shared repositories, mark `tests/` as test fixtures there. Shipped code under `plugins/` contains none.

## Changelog

[`CHANGELOG.md`](CHANGELOG.md) lists what changed in every release and what is waiting under `[Unreleased]`. Each pull request adds its line there and does not bump a version; releases are cut in a separate step. Rules, release steps and the PR template: [`CONTRIBUTING.md`](CONTRIBUTING.md). A test keeps the changelog in step with the version numbers.

## Tests
`python tests/run_all.py` runs 22 suites (about 930 checks: agent frontmatter, the SUBAGENTS.md roster, the `subagents-init` project setup tool, the changelog, browser guard, other guards, secret leak, kit tools, launcher, hook smoke, shell-helper and shell-purity tests, benchmark case loop, usage log checks, evaluation pipeline, safe-rm, rm routing, runner guard) four at a time; `--serial` runs them one after another and `-j N` sets the number at once. Each suite uses its own temporary data folder and never touches your real one. A parallel run takes about 3 minutes (several times longer in order) because each case starts a PowerShell process.

**On Ubuntu in Docker** (from a Linux shell or WSL with Docker; nothing is installed on the host and the container is removed afterwards): `sh tests/linux/run-in-docker.sh`. It builds `tests/linux/Dockerfile` (Ubuntu 24.04 + Python for the test runner only; no PowerShell: a test shim maps the PowerShell entry points to the `.sh` scripts), mounts the repository read-only, copies it inside the container and runs the same suites. Remove the image with `docker rmi agent-kit-ubuntu-test`.

## License
MIT, see `LICENSE`. This is software that runs hooks on your machine and is provided without warranty. If you use it in a regulated (GxP) setting, validating it for your intended use is your responsibility; the READMEs describe what each plugin does and does not guarantee.
