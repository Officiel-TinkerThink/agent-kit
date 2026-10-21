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
    return subprocess.run(["sh", str(SCRIPTS / "guard-proof-key.sh")], input=stdin_text, capture_output=True, text=True, encoding="utf-8", timeout=60)


def run_powershell(stdin_text):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPTS / "guard-proof-key.ps1")],
        input=stdin_text, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


def run_router(stdin_text):
    # The exact shape of the hook command in hooks/hooks.json, with CLAUDE_PLUGIN_ROOT set to the plugin folder.
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
]
ALLOWED = [
    'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec s.json --key-file /keys/k.txt',
    "node src/prove.js --key-file /keys/k.txt --verify",
    "node src/lab.js doctor",
    "ls -la",
    "npm run build --key x",
    'git commit -m "approve --key rotation"',
    'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec prove.json --key-file /keys/k.txt',
    # setup.mjs names no runner, so a cd prefix does not block it
    "cd /x && node setup.mjs --check-only",
    # the sanctioned doctor call: a variable outside the src/ file name is not a runner
    'node "$PROOF_LAB_HOME/src/lab.js" doctor',
    # node_modules is not the node word, and a glob in an ordinary command is not a node command (cycle-6 defect F2)
    "ls node_modules/*",
    "cat src/*.py",
    "grep -rn foo src/",
]
# Whole hook inputs, for the cases a plain command cannot express.
RAW_BLOCKED = [
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
        "description": "Command: check", "command": 'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec run-spec.json'}})),
    # a node word in a description field is not a node command (cycle-6 defect F2)
    ("node word only in the description", json.dumps({"tool_name": "Bash", "tool_input": {
        "description": "node {a,b} files", "command": "ls -la"}})),
]
UNREADABLE = [("not JSON", "not json"), ("empty input", "")]

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
    p = run(payload)
    if marker is None:
        return label, name, p.returncode == 0, f"exit {p.returncode} stderr {p.stderr!r}"
    return label, name, p.returncode == 2 and marker in p.stderr, f"exit {p.returncode} stderr {p.stderr!r}"


workers = int(os.environ.get("PROOF_LAB_GUARD_WORKERS", "12"))
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
