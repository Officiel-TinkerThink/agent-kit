"""The proof-lab key guard: blocks a command that puts the signing key in the environment or passes it inline.

Every case runs through three paths: the POSIX guard, its PowerShell twin, and the router the hook command calls
(run.sh picks one of the two by machine). A path that is not available on this machine is reported as skipped.
The rules are in docs/design/proof-lab-guard-v2.md.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "proof-lab"
P = PLUGIN.as_posix()  # the plugin root as Claude Code substitutes it in agent text (forward slashes)
SCRIPTS = PLUGIN / "scripts"
failed = 0


def check(name, cond, extra=""):
    global failed
    if cond:
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name} {extra}")


def run_posix(stdin_text):
    # 180 s: one POSIX guard call starts about 60 processes, which takes about 8 s under Git Bash on Windows and longer
    # while tests/run_all.py runs other suites at the same time (calls passed 60 s there). Linux and macOS take well
    # under a second; Windows runs the PowerShell twin in production.
    return subprocess.run(["sh", str(SCRIPTS / "guard-proof-key.sh")], input=stdin_text, capture_output=True, text=True, encoding="utf-8", timeout=180)


def run_powershell(stdin_text):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPTS / "guard-proof-key.ps1")],
        input=stdin_text, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


def run_router(stdin_text):
    # The exact shape of the hook command in hooks/hooks.json, as hooks/hooks.json runs it; the guard takes the plugin root from its own location.
    return subprocess.run(
        ["sh", str(SCRIPTS / "run.sh"), str(SCRIPTS / "guard-proof-key")],
        input=stdin_text, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


def bash(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


BLOCKED = [
    "PROOF_LAB_KEY=abc node src/run-spec.js --spec s.json",
    "export PROOF_LAB_KEY=abc",
    "echo $proof_lab_key",
    "node src/prove.js --key abc123 --spec s.json",
    "node src/prove.js --key=abc123",
    'PROOF_LAB_"KEY"=abc node src/run-spec.js --spec s.json',
    "node src/run-spec.js --spec s.json --key abc123",
    'node "$PROOF_LAB_HOME/src/run-spec.js" --spec s.json --key-file /keys/k.txt',
    "node src/run-spec.js --spec s.json --key-file /keys/k.txt",
    "node src/lab.js run --spec s.json --key-file /keys/k.txt",
    'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec s.json --key abc123',
    "npm run prove -- --key abc123",
    "node src/prove.js --url http://localhost:3000 --key-file /keys/k.txt",
    'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec s.json; node src/run-spec.js --spec s.json',
    "node src/prove.js --KEY abc",
    "node setup.mjs --check-only && node src/run-spec.js --spec s.json --key-file k.txt",
    # a verify call does not exempt a direct run of another runner in the same command
    "node src/run-spec.js --spec s.json --note prove.js --verify",
    # the runner named without its .js suffix
    "node src/run-spec --spec s.json --key-file /keys/k.txt",
    # the key flag at the end of the command, after the JSON quote is dropped
    'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec s.json --key',
    # a tab between the flag and its value (JSON-escaped as \t)
    "node setup.mjs --run --spec s.json --key\tabc123",
    # a newline chains a second command after a verify call
    "node src/prove.js --verify\nnode x",
    # a runner that is not the program of a closed form: behind a cd prefix, or inside sh -c
    "cd proof && node src/run-spec.js --spec s.json",
    "sh -c 'node src/run-spec.js --spec s.json'",
    # a runner followed by a comment that says "command:"
    "node src/run-spec.js --spec s.json # command: x",
    # a runner with no argument after it
    "node src/prove.js",
    # a newline escaped with an even run of backslashes is a real newline
    "node setup.mjs --run --spec s.json\\\\\nnode src/run-spec.js --spec s.json",
    # process substitution chains
    "node setup.mjs --run --spec s.json >(node src/run-spec.js --spec s.json)",
    # a glob in the program path names no runner word
    "node src/run-s*.js --spec s.json",
    # a glob after the program word, behind a cd prefix, and behind another word
    "cd proof && node src/run-s*.js --spec s.json",
    "node --no-warnings src/run-s*.js --spec s.json",
    # a variable in a src/ path names the runner at run time
    'node "$PROOF_LAB_HOME/src/$R.js" --spec s.json',
    # an option token before the program is not the program: the runner is the entry point (cycle-4 security F1)
    "node --import=/p/scripts/setup.mjs src/run-spec.js --spec s.json",
    # a brace expands to the runner name in the shell (cycle-4 defect F3)
    "node src/run-{spec,}.js --spec s.json",
    # a backslash inside the runner name is removed by the shell (cycle-4 defect F2)
    "node src/run\\-spec.js --spec s.json",
    # Windows backslash paths are refused: forward slashes only (decision in the v2 design)
    r"node D:\core\proof-lab\src\prove.js --verify",
    r"node D:\new\lab\src\prove.js --verify",
    r"node D:\core\proof-lab\src\prove.js --verify --key abc123",
    # the node word spelled with a backslash or in another case: the shell still runs node (cycle-6 security F2, guidance F2)
    "n\\\\ode src/run-s*.js --spec s.json",
    "\\\\node src/run-s*.js --spec s.json",
    "NODE src/run-s*.js --spec s.json",
    "n\\ode src/*",
    # a runner or script word with a glob, brace or backslash, with no node word (cycle-6 defect, security)
    "./src/run-{spec,}.js --spec s.json",
    "./src/run-s*.js --spec s.json",
    "./src/{ru,n}-spec.js --spec s.json",
    # the closed form is case-sensitive: prove.js reads --verify case-sensitively (cycle-6 security F1)
    "node src/prove.js --VERIFY --key-file /keys/k.txt",
    # setup.mjs runs the pin check only at the plugin's own path; a relative or other path is refused (cycle-6 spec F3)
    "node ./scripts/setup.mjs --run --spec s.json",
    "node ../scratch/setup.mjs --run --spec run-spec.json",
    "node $HOME/x/setup.mjs --run --spec s.json",
    # the glob is the last word of the command: the POSIX loop must read the unterminated final word (review cycle 7, defect F1)
    "cat ./src/*.js",
    "./src/run-s*.js",
    # a tab (JSON \t in the input) splits the word; the decoded text is checked as well (review cycle 7, spec F3)
    "cat x\tsetup* y",
    # a parent segment after the plugin root is not the plugin's own setup (review cycle 7, security F1)
    'node "${CLAUDE_PLUGIN_ROOT}/../x/setup.mjs" --run --spec s.json',
    # a literal ROOT is not the sanctioned placeholder (review cycle 7, spec F2)
    "node ROOT/scripts/setup.mjs --run --spec s.json",
    # the rewritten marker is reserved: a typed copy is refused, so only ${CLAUDE_PLUGIN_ROOT} reaches the closed form (review cycle 8, security F1 and spec F1)
    "node @PLUGIN_ROOT@/scripts/setup.mjs --run --spec s.json",
    'node "@PLUGIN_ROOT@/scripts/setup.mjs" --run --spec s.json',
    # the shell joins quoted pieces into the marker: the placeholder count of the value must not exceed the rewritten input (review cycle 8, security out-of-scope)
    "node @PLU''GIN_ROOT@/scripts/setup.mjs --run --spec s.json",
    # a single-quoted placeholder is not expanded by the shell, so it is refused
    "node '${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs' --run --spec s.json",
    # the closed form is matched on the command as written, so no quoting shape can build the sanctioned path (review cycle 9)
    'node @PLU""GIN_ROOT@/scripts/setup.mjs --run --spec s.json, note ${CLAUDE_PLUGIN_ROOT}',
    "node '\"${CLAUDE_PLUGIN_ROOT}\"'/scripts/setup.mjs --run --spec s.json",
    "node ' ${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs' --run --spec s.json",
    'node "${CLAUDE_PLUGIN_ROOT}"/scripts/setup.mjs --run --spec s.json',
    # an unquoted variable prefix is word-split by the shell, so the program is not the text the guard read (review cycle 11, security F1)
    "node $PROOF_LAB_HOME/src/prove.js --verify",
]
ALLOWED = [
    f'node "{P}/scripts/setup.mjs" --run --spec s.json --key-file /keys/k.txt',
    "node src/prove.js --key-file /keys/k.txt --verify",
    "node src/lab.js doctor",
    "ls -la",
    "npm run build --key x",
    'git commit -m "approve --key rotation"',
    f'node "{P}/scripts/setup.mjs" --run --spec prove.json --key-file /keys/k.txt',
    # setup.mjs names no runner, so a cd prefix does not block it
    "cd /x && node setup.mjs --check-only",
    # the sanctioned doctor call: a variable outside the src/ file name is not a runner
    'node "$PROOF_LAB_HOME/src/lab.js" doctor',
    # node_modules is not the node word, and a glob in an ordinary command is not a node command (cycle-6 defect F2)
    "ls node_modules/*",
    "cat src/*.py",
    "grep -rn foo src/",
    # the marker text and a placeholder in an ordinary command are plain text, not a runner (review cycle 9, over-blocks removed)
    "grep -rn @PLUGIN_ROOT@ plugins/proof-lab/scripts",
    "echo \"don't ${CLAUDE_PLUGIN_ROOT}\"",
    # the sanctioned setup path unquoted
    f"node {P}/scripts/setup.mjs --run --spec s.json --key-file /keys/k.txt",
    # a variable prefix inside the quoted program path is not word-split
    'node "$PROOF_LAB_HOME/src/prove.js" --verify',
]
# Whole hook inputs, for the cases a plain command cannot express.
RAW_BLOCKED = [
    # a no-break space (raw UTF-8, not a \u escape) is not a word separator in bash, so it cannot stand before --verify (review cycle 10, security F1)
    ("no-break space before --verify", json.dumps({"tool_name": "Bash", "tool_input": {
        "command": "node src/prove.js --key-file /keys/k.txt --verify"}}, ensure_ascii=False)),
    # a description that carries "command:" ahead of the real command must not hide the runner (cycle-4 spec F1, defect F4)
    ("description carries command: before the runner", json.dumps({"tool_name": "Bash", "tool_input": {
        "description": "command: node setup.mjs --run", "command": "node src/run-spec.js --spec s.json"}})),
]
RAW_ALLOWED = [
    # a description with no runner name does not stop a closed form
    ("closed form with a description", json.dumps({"tool_name": "Bash", "tool_input": {
        "description": "check the setup", "command": "node setup.mjs --check-only"}})),
    # a capitalised Command: in the description does not move the cut (cycle-6 defect F3)
    ("sanctioned run with Command: in the description", json.dumps({"tool_name": "Bash", "tool_input": {
        "description": "Command: check", "command": f'node "{P}/scripts/setup.mjs" --run --spec run-spec.json'}})),
    # a node word in a description field is not a node command (cycle-6 defect F2)
    ("node word only in the description", json.dumps({"tool_name": "Bash", "tool_input": {
        "description": "node {a,b} files", "command": "ls -la"}})),
    # the hook input exactly as Claude Code sent it for the proof-runner agent (captured 2026-10-21): compact JSON, agent
    # fields, and a trailing newline, which is JSON whitespace, not a chain (the PowerShell twin refused every run before)
    ("real proof-runner hook input with a trailing newline", json.dumps({
        "session_id": "00000000-0000-4000-8000-000000000000", "transcript_path": "C:\\Users\\u\\.claude\\projects\\p\\s.jsonl",
        "cwd": "D:\\core\\projects\\proof-lab", "prompt_id": "00000000", "permission_mode": "default",
        "agent_id": "a0000000000000000", "agent_type": "proof-lab:proof-runner", "effort": {"level": "low"},
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": f'node "{PLUGIN.as_posix()}/scripts/setup.mjs" --run --spec D:/core/projects/proof-lab/demo/specs/06-error-invalid-spec.json'
                       " --key-file C:/Users/USER~1.ACC/AppData/Local/Temp/proof-lab-demo-x/demo.key --json",
                       "description": "Run proof-lab spec 06 with the demo key file"},
        "tool_use_id": "toolu_01EXAMPLE"}, separators=(",", ":")) + "\n"),
    # a description whose value is the word "command" is not the key: the cut needs the colon on both twins (backlog item 21)
    ("description equal to the word command", json.dumps({"tool_name": "Bash", "tool_input": {
        "description": "command", "command": f'node "{P}/scripts/setup.mjs" --run --spec s.json'}})),
]
UNREADABLE = [("not JSON", "not json"), ("empty input", "")]

# The command the real proof-runner agent typed (headless run, 2026-10-21): Claude Code substitutes ${CLAUDE_PLUGIN_ROOT}
# in agent text with the absolute root (forward slashes on Windows), and the agent quotes its arguments. The guard takes
# its own root from its location, so only that root matches.
RAW_BLOCKED += [
    # a raw newline inside the command string would be a separator for the shell; only a trailing one is whitespace
    # (review cycle 14, security F1 and defect F1)
    ("raw newline inside the command string", '{"tool_name":"Bash","tool_input":{"command":"node \\"' + P
     + '/scripts/setup.mjs\\" --run --spec s.json\nrm -rf /tmp/x"}}'),
    # a raw carriage return is not a separator to bash: "k.txt<CR>--verify" is one argument, so prove.js would run
    # without --verify (review cycle 15, defect unclear item)
    ("raw carriage return before --verify", '{"tool_name":"Bash","tool_input":{"command":"node src/prove.js --key-file /keys/k.txt\r--verify"}}'),
]
RAW_ALLOWED += [
    # trailing whitespace of any kind is dropped on both twins (review cycle 15, defect F1)
    ("sanctioned run with trailing CRLF and a space", json.dumps({"tool_name": "Bash", "tool_input": {
        "command": f'node "{P}/scripts/setup.mjs" --run --spec s.json'}}, separators=(",", ":")) + "\r\n \n"),
]
ALLOWED += [
    f'node "{P}/scripts/setup.mjs" --run --spec "D:/core/projects/proof-lab/demo/specs/06-error-invalid-spec.json"'
    ' --key-file "C:/Users/USER~1.ACC/AppData/Local/Temp/proof-lab-demo-x/demo.key" --json',
    f"node {P}/scripts/setup.mjs --run --spec s.json --key-file /keys/k.txt",
]
BLOCKED += [
    # the same run wrapped in a chain, as the agent first wrote it
    f'if [ -z "$PROOF_LAB_HOME" ]; then exit 2; fi; node "{P}/scripts/setup.mjs" --run --spec s.json',
    # a parent segment, a longer root, and another plugin's setup.mjs are not this plugin's setup
    f'node "{P}/../x/setup.mjs" --run --spec s.json',
    f'node "{P}x/scripts/setup.mjs" --run --spec s.json',
    f'node "{PLUGIN.parent.as_posix()}/agent-guards/scripts/setup.mjs" --run --spec s.json',
    # the literal placeholder is expanded by the shell from an environment the guard does not read (unset, it gives
    # /scripts/setup.mjs), so only the exact root is a closed form (review cycle 14, security F2)
    'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec s.json --key-file /keys/k.txt',
    "node ${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs --run --spec s.json",
    # ) is a shell operator that ends a word, so it cannot hide the node word from the node glob check (backlog item 30)
    "a)node src/*",
    # the variable prefix of prove.js must be balanced (backlog item 34)
    'node "$PROOF_LAB_HOME}/src/prove.js" --verify',
]
RAW_BLOCKED += [
    # a trailing no-break space is not in the ASCII whitespace set both twins trim, so both refuse the input alike
    # (backlog item 29: PowerShell used to trim it with .NET's Unicode set while sh kept it)
    ("trailing no-break space", json.dumps({"tool_name": "Bash", "tool_input": {
        "command": f'node "{P}/scripts/setup.mjs" --run --spec s.json'}}, separators=(",", ":")) + " "),
]

paths = [("posix", run_posix), ("powershell", run_powershell), ("router", run_router)]
# PROOF_LAB_GUARD_PATHS=powershell,router limits the run; the POSIX guard takes seconds per call under Git Bash on Windows.
import os
only = os.environ.get("PROOF_LAB_GUARD_PATHS")
if only:
    wanted = [name.strip() for name in only.split(",") if name.strip()]
    unknown = [name for name in wanted if name not in dict(paths)]
    if unknown or not wanted:
        sys.exit(f"PROOF_LAB_GUARD_PATHS names no known path: {unknown or only!r}; use posix, powershell, router")
    paths = [p for p in paths if p[0] in wanted]
if shutil.which("sh") is None:
    print("skip proof-lab guard: sh is not on PATH (Git Bash on Windows)")
    sys.exit(0)

# Each case is one independent process, so they run concurrently; results are printed in case order.
# Each job: (label, name, run, payload, expect_blocked, must_contain). Blocked cases need exit 2 and BLOCKED,
# allowed cases exit 0, unreadable input exit 2 with "guard error".
jobs = []
for label, run in paths:
    if label == "powershell" and shutil.which("powershell.exe") is None:
        print("skip proof-lab guard (powershell): powershell.exe is not on PATH")
        continue
    for command in BLOCKED:
        jobs.append((label, f"blocks: {command!r}", run, bash(command), "BLOCKED"))
    for command in ALLOWED:
        jobs.append((label, f"allows: {command}", run, bash(command), None))
    for name, payload in RAW_BLOCKED:
        jobs.append((label, f"blocks: {name}", run, payload, "BLOCKED"))
    for name, payload in RAW_ALLOWED:
        jobs.append((label, f"allows: {name}", run, payload, None))
    for name, payload in UNREADABLE:
        jobs.append((label, f"blocks unreadable input ({name})", run, payload, "guard error"))


def execute(job):
    label, name, run, payload, marker = job
    try:
        p = run(payload)
    except subprocess.TimeoutExpired:
        # one slow call is a failed case, not a crash of the whole run
        return label, name, False, "timed out"
    if marker is None:
        return label, name, p.returncode == 0, f"exit {p.returncode} stderr {p.stderr!r}"
    return label, name, p.returncode == 2 and marker in p.stderr, f"exit {p.returncode} stderr {p.stderr!r}"


# Four workers by default: tests/run_all.py already runs several suites at once, and each POSIX guard call spawns about
# 60 processes, which Git Bash on Windows starts slowly; more workers made calls exceed the 60 s timeout under the gate.
workers = int(os.environ.get("PROOF_LAB_GUARD_WORKERS", "4"))
with ThreadPoolExecutor(max_workers=workers) as pool:
    for label, name, ok, extra in pool.map(execute, jobs):
        check(f"{label} {name}", ok, extra)

# The router fails closed: with PowerShell missing from PATH, the hook exits 2 (blocks), not some other code (lets the call through).
no_ps = subprocess.run(
    ["sh", str(SCRIPTS / "run.sh"), str(SCRIPTS / "guard-proof-key")],
    input=bash("node src/run-spec.js --spec s.json"), capture_output=True, text=True, encoding="utf-8", timeout=60,
    env={"PATH": str(pathlib.Path(shutil.which("sh")).parent), "AGENT_KIT_SHELL": "ps"},
)
check("router fails closed when powershell.exe is missing", no_ps.returncode == 2 and "powershell.exe" in no_ps.stderr, f"exit {no_ps.returncode} stderr {no_ps.stderr!r}")

sys.exit(1 if failed else 0)
