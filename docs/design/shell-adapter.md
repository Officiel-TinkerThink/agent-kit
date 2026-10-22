# Shell adapter: one contract, machine-routed implementations

Status: proposed. Owner: agent-kit maintainers.

## Problem

Every kit capability exists as two implementations: `<name>.ps1` (Windows PowerShell 5.1) and `<name>.sh` (POSIX sh). Callers and tests chose between them by hand. The test suites hard-code `PWSH = 'powershell.exe' if win32 else 'pwsh'`, so on Linux they ran PowerShell, which is not installed there. Nine suites failed on Linux for that reason. Skipping them would hide the gap, so this design removes the choice from callers instead.

## Design

1. **One contract per capability.** A capability has one name (for example `guard-shell-os`) and one interface: stdin (hook JSON or arguments), stdout, stderr and an exit code (0 allow or success, 2 block or fail closed). The contract is the same on every machine.
2. **One adapter decides, by OS.** `plugins/<plugin>/scripts/run.sh <name>` is the only place that picks an implementation. The rule is the operating system, not a binary on PATH:
   - Windows (`uname` reports `MINGW*`, `MSYS*` or `CYGWIN*`) with `powershell.exe` present: `<name>.ps1`. The `OS` variable is not used, because it can leak into WSL through WSLENV.
   - Linux and macOS: `<name>.sh`. WSL counts as Linux (`uname` reports `Linux` and `/proc/version` contains `microsoft`), even though `powershell.exe` is reachable through the Windows PATH that WSL appends.
   - Windows without `powershell.exe` (for example a machine with only `pwsh`) exits 2. It is not routed to `.sh` silently, and `pwsh` is not accepted as the Windows binary unless the open decision below says so.
   - Override: `AGENT_KIT_SHELL=ps|posix` forces one implementation. Every override is written to the audit line (item 7).
   - A missing implementation exits 2, so a guard that cannot run blocks instead of being skipped.
3. **Callers never name a shell.** Hooks, skills, tests and documentation call `run.sh <name>`. No caller passes `pwsh`, `powershell`, `.ps1` or `.sh`.
4. **Parity is enforced by a shared case table, not by file names.** Each capability has one case file (for example `tests/agent-guards/cases/guard-shell-os.json`). Every case lists the stdin, the expected exit code, the expected stdout JSON (exact match) and an expected stderr fragment. The same table runs against both implementations.
   - Each name must have both files. `tests/agent-guards/test_shell_os.py` checks the `.ps1` to `.sh` direction and the reverse.
   - Limit: a Linux machine has no `pwsh`, so the `.ps1` side runs only on Windows. Cross-machine parity is therefore proven by the same expected outputs run on each machine's implementation, not by one run of both. This limit is stated in the validation evidence.
   - A test that fails on one machine is a parity gap to fix, not a reason to skip.
5. **Agents are told the machine's shell.** The SessionStart text names the shell on this machine (done for `agent-guards`).
6. **Agent tool calls cannot be routed by us.** A `PowerShell` tool call on a machine without PowerShell is blocked by `guard-shell-os.sh`, and the block message names the adapter command to use instead. This guards against accidental use only; `eval`, base64 or a script file bypass it.
7. **Audit trail.** Every `run.sh` call appends one line to `<kit data>/verification-logs/_shell_routing.jsonl`, before the capability runs: UTC time, capability, chosen implementation (`ps` or `posix`), reason (`os` or `override`), and the `uname` value. The exit code is not recorded, because `run.sh` replaces itself with the capability (`exec`); the capability's own logs carry its outcome. A line that cannot be written blocks the call (decision 2). Validation evidence per machine lists the chosen implementation for each capability. Open decision below: whether a failed audit write blocks the call (proposed: yes, fail closed).
8. **Callers-never-name-a-shell is enforced by a test.** A test scans every `plugins/*` file (hooks, skills, agents, commands, docs) and fails on `pwsh`, `powershell`, `.ps1` or `.sh` outside `run.sh`, the adapter's own files and the `guard-shell-os` pair. A convention that no test enforces is not a control.

## Migration of the nine PowerShell-only suites

- Replace `[PWSH, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', HOOK]` with one helper `run_capability(name, stdin=..., args=..., env=...)` that calls `sh run.sh <path-without-extension>`. The `PWSH` constant goes away.
- Tests that copy a hook to a temp folder (`test_guard_browser.py:155`, `test_guard_rm_routing.py:189`) keep copying both siblings, so the adapter finds both.
- Assertions that depend on Windows-only behaviour (junctions, `%LOCALAPPDATA%`, `cmd /c mklink`) stay behind a platform check inside the test, with the reason. Those checks are narrow and named, not a whole-suite skip.
- Each suite runs on both machines: Windows through `run_all.py`, Linux through the Docker run.

## Rules for the migration

These apply to every suite and every guard touched by the migration.

- **No silent skips.** A platform branch names its reason in code. The runner fails if a skip has no reason or a reason not on a short allow-list. The summary line counts skipped checks (`N/M passed, K not applicable: <reasons>`); a `0/0 passed (skipped)` line is a failure.
- **Named checks, not whole-suite skips.** A Windows-only assertion (junctions, `%LOCALAPPDATA%`, `cmd /c mklink`) is its own named check, for example `check_junction_on_windows`, counted in the summary.
- **Guard output contract is the same on both implementations.** Allow: the same stdout JSON (for example `hookSpecificOutput`), byte for byte. Block: exit 2 and the same stderr fragment. Both are in the shared case table (item 4).
- **Windows prerequisite.** Git for Windows (`sh`) is required, because hooks run through `sh run.sh`. SessionStart names the implementation chosen on that machine.
- **Git Bash changes arguments before the adapter runs (measured 2026-10-18).** `sh.exe` expands wildcards in its own argument list (`app/*/f.txt` becomes the real files it matches) unless `MSYS=noglob` is set in its environment. `run.sh` cannot undo this, so every caller on Windows must set it: `tests/capability.py` does. `run.sh` itself turns off MSYS path conversion (`/etc/passwd` and a path with a space were rewritten before the PowerShell call) and passes the script as a Windows path (`cygpath -w`).
- **Changing an assertion needs a note.** If a migrated assertion checks PowerShell-specific output and is changed to pass on Linux, the migration PR records the test, the old assertion, the new assertion and the reason. Without that note the assertion is not changed.

## Decisions (resolved by the maintainer, 2026-10-18)

1. **Windows binary: `powershell.exe` only.** `pwsh` is not accepted. A Windows machine without `powershell.exe` fails closed (exit 2).
2. **Failed audit write blocks the call (fail closed).** An audit line that cannot be written is a missing evidence record, so the call does not run.
3. **`AGENT_KIT_SHELL` is set by the machine owner only**, through the environment of the machine, never by a project file. A project cannot route its own guards.
4. **Claude Code tool names (researched 2026-10-18, from code.claude.com docs; partly from page extraction, not byte-verified):**
   - The shell tools are `Bash` and `PowerShell`.
   - On Linux, macOS and WSL the `PowerShell` tool is opt-in (`CLAUDE_CODE_USE_POWERSHELL_TOOL=1`) and needs PowerShell 7 (`pwsh`) on PATH. By default it is not registered on Linux, so item 6 blocks only when the user opted in.
   - The documented hook matcher for shell-inspecting hooks is `Bash|PowerShell`. `hooks.json` uses `PowerShell|Bash`, which matches the same two tools.
   - Hook `shell` defaults to `bash`, not PowerShell, on Linux.
   - Not verified: the exact `tool_name` string in hook input (documentation gives no literal example), and the Claude Code version that introduced the `PowerShell` tool.
5. **No `pwsh` on Linux, ever.** Linux runs only the native `.sh` implementations. No `pwsh` executor, shim or emulator is installed or invented on Linux (the former `tests/linux/pwsh` shim was removed).

## Hook input and hook failures (2026-10-22)

- **`run.sh --hook` reads the hook input with a time limit.** Every `hooks.json` command passes `--hook`. The launcher copies stdin to a temporary file for at most 5 seconds (a background `cat` and a timer, not `timeout(1)`, which under Git Bash can resolve to the Windows `timeout.exe`) and gives the script that file as stdin. A script that reads to the end of its input (`[Console]::In.ReadToEnd()`, `$(cat)`) therefore always returns. Before, a pipe the harness left open kept the guard waiting until the 30-second hook timeout killed it (measured: 40 s with stdin held open 40 s). What arrived in time is passed on; a limit that expires is traced in `hook-errors.log`. Skills and tools call `run.sh` without `--hook` and keep reading their whole input.
- **A guard blocks only a call it has identified as in scope.** Input it cannot read, or a caller it does not apply to, is allowed. A guard for one agent (`guard-verification-runner`, `guard-git-readonly`, `guard-annotator`) fails closed only once it knows the caller is that agent.
- **`onFailure: block` only where every call is in scope.** A hook that times out or crashes decided nothing, and with `onFailure: block` Claude Code refuses the call anyway, for every agent and the main thread. Only `guard-browser` keeps it: its matcher is the browser tools, and every browser call is in its scope. `guard-proof-key` has no `onFailure` and keeps its own fail-closed rule for unreadable input, because every Bash call is in its scope (`docs/design/proof-lab-guard-v2.md`). `tests/agent-guards/test_launcher.py` checks both rules for all `hooks.json` files.

Implementation status: implemented in `plugins/*/scripts/run.sh` (routing, the `AGENT_KIT_SHELL` override, `powershell.exe`-only on Windows, the fail-closed audit line) and in `guard-shell-os` (item 6). Tested by `tests/agent-guards/test_shell_os.py` and the full suite on Windows and on Linux (Docker). Not yet built: the shared case tables of item 4 for the parity suites (listed in the PR body as the parity gap).

## Out of scope

- Converting a `.ps1` implementation to POSIX is a per-capability change. Each one needs its own parity test.
- Calls hidden inside `eval`, base64 or script files are not seen by `guard-shell-os`; it guards against accidental use.
