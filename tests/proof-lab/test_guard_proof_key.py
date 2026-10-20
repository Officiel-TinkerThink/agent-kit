"""The proof-lab key guard: blocks a command that puts the signing key in the environment or passes it inline.

Every case runs through three paths: the POSIX guard, its PowerShell twin, and the router the hook command calls
(run.sh picks one of the two by machine). A path that is not available on this machine is reported as skipped.
"""
import json
import pathlib
import shutil
import subprocess
import sys

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
]
ALLOWED = [
    'node "${CLAUDE_PLUGIN_ROOT}/scripts/setup.mjs" --run --spec s.json --key-file /keys/k.txt',
    "node src/prove.js --key-file /keys/k.txt --verify",
    "node src/lab.js doctor",
    "ls -la",
    "npm run build --key x",
    'git commit -m "approve --key rotation"',
]
UNREADABLE = [("not JSON", "not json"), ("empty input", "")]

paths = [("posix", run_posix), ("powershell", run_powershell), ("router", run_router)]
if shutil.which("sh") is None:
    print("skip proof-lab guard: sh is not on PATH (Git Bash on Windows)")
    sys.exit(0)

for label, run in paths:
    if label == "powershell" and shutil.which("powershell.exe") is None:
        print("skip proof-lab guard (powershell): powershell.exe is not on PATH")
        continue
    for command in BLOCKED:
        p = run(bash(command))
        check(f"{label} blocks: {command}", p.returncode == 2 and "BLOCKED" in p.stderr, f"exit {p.returncode} stderr {p.stderr!r}")
    for command in ALLOWED:
        p = run(bash(command))
        check(f"{label} allows: {command}", p.returncode == 0, f"exit {p.returncode} stderr {p.stderr!r}")
    for name, payload in UNREADABLE:
        p = run(payload)
        check(f"{label} blocks unreadable input ({name})", p.returncode == 2 and "guard error" in p.stderr, f"exit {p.returncode} stderr {p.stderr!r}")

# The router fails closed: with PowerShell missing from PATH, the hook exits 2 (blocks), not some other code (lets the call through).
no_ps = subprocess.run(
    ["sh", str(SCRIPTS / "run.sh"), str(SCRIPTS / "guard-proof-key")],
    input=bash("node src/run-spec.js --spec s.json"), capture_output=True, text=True, encoding="utf-8", timeout=60,
    env={"PATH": str(pathlib.Path(shutil.which("sh")).parent), "AGENT_KIT_SHELL": "ps"},
)
check("router fails closed when powershell.exe is missing", no_ps.returncode == 2 and "powershell.exe" in no_ps.stderr, f"exit {no_ps.returncode} stderr {no_ps.stderr!r}")

sys.exit(1 if failed else 0)
