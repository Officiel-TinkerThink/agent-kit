"""Tests for the POSIX shell guard (guard-shell-os.sh), its Windows twin, the SessionStart machine-shell line, and the rule that
every PowerShell script under plugins/*/scripts has a POSIX twin. Needs sh on PATH; runs on Linux and Windows.
Run: python test_shell_os.py"""
import json, pathlib, shutil, subprocess, sys

PLUGINS = pathlib.Path(__file__).resolve().parents[2] / 'plugins'
SCRIPTS = PLUGINS / 'agent-guards' / 'scripts'
GUARD = SCRIPTS / 'guard-shell-os.sh'
SESSION = SCRIPTS / 'session-context.sh'
SH = shutil.which('sh')

results = []


def check(name, ok):
    results.append((name, ok))
    print(('PASS ' if ok else 'FAIL ') + name)


def bash(cmd):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})


def run_sh(script, stdin):
    p = subprocess.run([SH, str(script)], input=stdin, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


# (name, hook payload, expected exit code). 2 = blocked, 0 = allowed.
GUARD_CASES = [
    ("PowerShell tool call is blocked",
     json.dumps({"tool_name": "PowerShell", "tool_input": {"command": "Get-ChildItem"}}), 2),
    ("pwsh -File is blocked", bash("pwsh -File scripts/x.ps1"), 2),
    ("powershell.exe -Command is blocked", bash("powershell.exe -Command ls"), 2),
    ("pwsh after a semicolon is blocked", bash("echo hi; pwsh -c ls"), 2),
    ("powershell after && is blocked", bash("cd x && powershell -c ls"), 2),
    ("pwsh inside sh -c quotes is blocked", bash('sh -c "pwsh -c ls"'), 2),
    ("plain ls is allowed", bash("ls -la"), 0),
    ("the word powershell in echo is allowed", bash("echo powershell"), 0),
    ("a file named powershell.txt is allowed", bash("cat powershell.txt"), 0),
    ("Read tool is not touched", json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}}), 0),
    ("unparseable input is allowed (fail-open)", "not json", 0),
]

for name, payload, expected in GUARD_CASES:
    code, _, _ = run_sh(GUARD, payload)
    check(f"guard: {name}", code == expected)

# A blocked call must name the POSIX alternative on stderr.
_, _, err = run_sh(GUARD, bash("pwsh -c ls"))
check("guard: block message names the POSIX alternative", 'POSIX' in err and 'sh version' in err)

# SessionStart: the machine-shell line comes first and the guards policy follows it.
code, out, _ = run_sh(SESSION, "")
check("session-context: exits 0", code == 0)
check("session-context: states the machine shell first",
      out.splitlines()[:1] and out.splitlines()[0].startswith('Machine shell: POSIX sh'))

# Parity: every PowerShell script has a POSIX twin, so run.sh never has to block on a missing version.
missing = [str(p.relative_to(PLUGINS)) for p in sorted(PLUGINS.glob('*/scripts/*.ps1'))
           if not p.with_suffix('.sh').exists()]
check(f"parity: every .ps1 has a .sh twin (missing: {missing or 'none'})", not missing)

failed = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - failed}/{len(results)} passed")
sys.exit(1 if failed else 0)
