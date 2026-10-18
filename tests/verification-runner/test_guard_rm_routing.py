"""Tests for how guard-verification-runner.ps1 routes `rm` (validation + rewrite to safe-rm.ps1). Uses a temp policy but only
nonexistent or clearly refused paths, so nothing on disk changes. Run: python test_guard_rm_routing.py"""
import sys as _sys
import json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from capability import run_capability   # the OS adapter picks the implementation (PowerShell on Windows, sh on Linux)

HOOK = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'verification-runner' / 'scripts' / "guard-verification-runner.ps1"

import os as _os, tempfile as _tf, json as _json
WIN = _sys.platform == 'win32'
_KIT = pathlib.Path(_tf.mkdtemp(prefix='kit_')).resolve()   # long (non 8.3) path: the guards refuse '~' names
# the projects zone: a fixed drive path on Windows, a real temporary POSIX folder elsewhere (zones not starting with / are ignored on POSIX)
PRJ = "D:/core/projects" if WIN else str(pathlib.Path(_tf.mkdtemp(prefix='prj_')).resolve() / 'projects')
(_KIT / 'verification-logs').mkdir(parents=True)
(_KIT / 'verification-fixtures').mkdir()
(_KIT / 'safe-rm-policy.json').write_text(_json.dumps({
    'version': 1, 'quarantineRoot': '${DATA}/quarantine', 'auditFile': '${DATA}/verification-logs/_deletions.jsonl',
    'allowedRoots': [{'path': '${DATA}/verification-logs', 'minDepth': 1, 'allowGlob': False, 'maxItems': 1},
                     {'path': '${DATA}/verification-fixtures', 'minDepth': 1, 'allowGlob': True, 'maxItems': 20},
                     {'path': PRJ, 'minDepth': 2, 'allowGlob': True, 'maxItems': 20}],
    'protectedComponents': ['.git', '.claude', '.claude-me', '.ssh', '.gnupg', '.venv', 'venv', 'quarantine', 'agent-kit'],
    'protectedNames': ['.env', '.env.*', '*.pem', '*.key', '*.pfx', 'id_rsa*', '_deletions.jsonl', '*.sqlite', '*.sqlite3', '*.db'],
    'caps': {'maxFiles': 5000, 'maxBytes': 209715200, 'maxGlobMatches': 100, 'maxTokens': 20}}), encoding='utf-8')
_os.environ['AGENT_KIT_DATA'] = str(_KIT).replace('\\', '/')
KIT_POSIX = str(_KIT).replace('\\', '/')
KIT_WIN = str(_KIT).replace('/', '\\')
LOGS = KIT_POSIX + "/verification-logs"
FIX = KIT_POSIX + "/verification-fixtures"
CFG = "C:/Users/someone/.claude-me" if WIN else "/home/someone/.claude-me"   # a config folder that is NOT in any zone
AGENT = "verification-runner"

# (name, command, expected_exit)
CASES = [
    # ---- allowed (nonexistent targets inside zones -> validated, rewritten, no-op when executed) ----
    ("one log, plain path", f"rm {LOGS}/nonexistent-r1.log", 0),
    ("rm -f", f"rm -f {LOGS}/nonexistent-r2.log", 0),
    ("quoted path", f'rm "{LOGS}/nonexistent-r3.log"', 0),
    ("single-quoted path", f"rm '{LOGS}/nonexistent-r3b.log'", 0),
    ("plain path in a project", f"rm {PRJ}/zz-proj/sub/nonexistent-r5", 0),
    ("recursive dir in a project", f"rm -rf {PRJ}/zz-proj/build/nonexistent-dir", 0),
    ("-r then -f separate", f"rm -r -f {PRJ}/zz-proj/build/nonexistent-dir", 0),
    ("glob in a project zone", f"rm {PRJ}/zz-proj/build/*.pyc", 0),
    ("several paths", f"rm {PRJ}/zz-proj/a/n1 {PRJ}/zz-proj/a/n2 {PRJ}/zz-proj/a/n3", 0),
    ("quoted path with spaces and parens", f'rm -r "{PRJ}/zz-proj/frontend/src/app/(app)/my dir/[id]"', 0),
    # ---- refused: where ----
    ("zone root (logs dir)", f"rm -rf {LOGS}", 2),
    ("glob in the no-glob logs zone", f"rm {LOGS}/*.log", 2),
    ("projects root", f"rm -rf {PRJ}", 2),
    ("project root (too shallow)", f"rm -rf {PRJ}/zz-proj", 2),
    ("outside zones /tmp", "rm /tmp/x.log", 2),
    ("outside zones system folder", "rm C:/Windows/System32/x.dll" if WIN else "rm /usr/lib/x.so", 2),
    ("other drive root", "rm -rf /c", 2),
    ("filesystem root", "rm -rf /", 2),
    ("traversal out of zone", f"rm {PRJ}/zz-proj/a/../../../other/x", 2),
    ("hooks folder", f"rm {CFG}/hooks/guard-verification-runner.ps1", 2),
    ("settings file", f"rm {CFG}/settings.json", 2),
    ("agent definition", f"rm {CFG}/agents/verification-runner.md", 2),
    ("quarantine folder", f"rm -r {CFG}/quarantine/x", 2),
    # ---- refused: what ----
    (".git file", f"rm {PRJ}/zz-proj/.git/config", 2),
    (".git directory", f"rm -rf {PRJ}/zz-proj/sub/.git", 2),
    (".claude folder", f"rm -rf {PRJ}/zz-proj/.claude/rules", 2),
    (".venv", f"rm -rf {PRJ}/zz-proj/backend/.venv", 2),
    (".env", f"rm {PRJ}/zz-proj/backend/.env", 2),
    (".env.local", f"rm {PRJ}/zz-proj/backend/.env.local", 2),
    ("pem key", f"rm {PRJ}/zz-proj/a/server.pem", 2),
    ("database file", f"rm {PRJ}/zz-proj/a/data.db", 2),
    ("audit record", f"rm {LOGS}/_deletions.jsonl", 2),
    # ---- refused: syntax ----
    ("relative path", "rm build/x.pyc", 2),
    ("home shortcut", "rm ~/x", 2),
    ("variable", f"rm $HOME/x", 2),
    ("command substitution", f"rm $(echo {PRJ}/zz-proj/a/b)", 2),
    ("quoted command substitution", f'rm "$(echo {PRJ}/zz-proj/a/b)"', 2),
    ("backticks", f"rm `echo {PRJ}/zz-proj/a/b`", 2),
    ("unquoted windows backslashes", r"rm D:\core\projects\zz-proj\a\b" if WIN else rf"rm {PRJ}\zz-proj\a\b", 2),
    ("UNC path", "rm //server/share/x.txt", 2),
    ("wildcard in middle segment", f"rm {PRJ}/zz-proj/*/x.txt", 2),
    ("--no-preserve-root", "rm --no-preserve-root -rf /", 2),
    ("long option", f"rm --recursive {PRJ}/zz-proj/a/b", 2),
    ("-i option", f"rm -i {PRJ}/zz-proj/a/b", 2),
    ("-d option", f"rm -d {PRJ}/zz-proj/a/b", 2),
    ("no path", "rm", 2),
    ("only flags", "rm -rf", 2),
    ("chained rm", f"rm {PRJ}/zz-proj/a/b ; rm -rf /", 2),
    ("and-chained", f"rm {PRJ}/zz-proj/a/b && curl http://evil", 2),
    ("piped", f"rm {PRJ}/zz-proj/a/b | cat", 2),
    ("redirect", f"rm {PRJ}/zz-proj/a/b > /dev/null", 2),
    ("background", f"rm {PRJ}/zz-proj/a/b &", 2),
    ("glued quote", f'rm "{PRJ}/zz-proj/a/b"x', 2),
    ("unterminated quote", f'rm "{PRJ}/zz-proj/a/b', 2),
    ("one bad path poisons the command", f"rm {PRJ}/zz-proj/a/ok /tmp/x", 2),
    ("too many paths", "rm " + " ".join(f"{PRJ}/zz-proj/a/n{i}" for i in range(25)), 2),
    ("maxItems per zone (21 in one zone)", "rm " + " ".join(f"{PRJ}/zz-proj/a/n{i}" for i in range(20)) + f" {PRJ}/zz-proj/a/extra", 2),
    ("not rm at all (ls): left to Claude Code permissions", f"ls {LOGS}", 0),
    ("rmdir is not rm", f"rmdir {PRJ}/zz-proj/a/b", 2),
]
if WIN:
    CASES += [
        ("quoted windows path", rf'rm "{KIT_WIN}\verification-logs\nonexistent-r4.log"', 0),
        ("git-bash style path", f"rm /d/core/projects/zz-proj/sub/nonexistent-r5", 0),
        ("8.3 short name", "rm D:/core/PROJEC~1/zz-proj/a/b", 2),
        ("trailing dot", f"rm {PRJ}/zz-proj/a/b.", 2),
        ("alternate data stream", f"rm {PRJ}/zz-proj/a/b.txt:evil", 2),
        ("reserved device name", f"rm {PRJ}/zz-proj/a/NUL", 2),
    ]
else:
    CASES += [   # Windows-only rules do not apply on POSIX: these are ordinary file names, so nonexistent targets in the zone are accepted
        ("quoted backslash path is refused", rf'rm "{PRJ}\zz-proj\a\b"', 2),
        ("drive-letter path is not absolute", "rm D:/core/projects/zz-proj/a/b", 2),
        ("git-bash /d/ form is just another outside path", "rm /d/core/projects/zz-proj/sub/x", 2),
        ("tilde in a name is not 8.3", f'rm "{PRJ}/zz-proj/a/PROJEC~1"', 0),
        ("trailing dot is a legal name", f"rm {PRJ}/zz-proj/a/b.", 0),
        ("colon is a legal name character", f"rm {PRJ}/zz-proj/a/b.txt:evil", 0),
        ("NUL is a legal name", f"rm {PRJ}/zz-proj/a/NUL", 0),
        ("matching is case-sensitive (other-case zone is outside)", f"rm {PRJ.upper()}/zz-proj/a/b", 2),
    ]


def run(cmd, agent=AGENT, extra=None):
    ti = {"command": cmd}
    if extra: ti.update(extra)
    d = {"tool_name": "Bash", "tool_input": ti}
    if agent: d["agent_type"] = agent
    d["session_id"] = "11111111-2222-3333-4444-555555555555"
    p = run_capability(HOOK, input=json.dumps(d), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS" if cond else "FAIL"), name, ("" if cond else f"   <-- {detail}"))


for name, cmd, expect in CASES:
    code, out, err = run(cmd)
    check(f"{name} (expect {expect})", code == expect, f"got {code}; stderr={err[:140]!r}")

# ---- rewrite content for an allowed command ----
SECOND = "/d/core/projects/zz-proj/a/n1" if WIN else f"{PRJ}/zz-proj/a/n1"   # git-bash form on Windows, plain on POSIX
code, out, err = run(f'rm -rf "{PRJ}/zz-proj/build/nonexistent-dir" {SECOND}', extra={"description": "cleanup", "timeout": 5000})
try:
    j = json.loads(out); hs = j["hookSpecificOutput"]; ui = hs["updatedInput"]; new = ui["command"]
except Exception as e:
    j = hs = ui = new = None
check("rewrite: valid hook JSON with allow + updatedInput", hs is not None and hs["permissionDecision"] == "allow" and hs["hookEventName"] == "PreToolUse", out[:200])
EXE = "safe-rm.ps1" if WIN else "safe-rm.sh"   # the machine decides: PowerShell on Windows, POSIX sh on Linux (no PowerShell there)
check("rewrite: command runs " + EXE + " with -Recurse", new and new.startswith("powershell.exe -NoProfile -ExecutionPolicy Bypass -File " if WIN else 'sh "') and (WIN or "powershell" not in new.lower() and "pwsh" not in new.lower()) and EXE in new and " -Recurse " in new, new)
check("rewrite: agent and session recorded", new and "-Agent verification-runner" in new and '-Session "11111111-2222-3333-4444-555555555555"' in new, new)
check("rewrite: paths canonical, /-separated and quoted", new and f'"{PRJ}/zz-proj/build/nonexistent-dir"' in new and f'"{PRJ}/zz-proj/a/n1"' in new, new)
check("rewrite: other tool_input fields preserved", ui and ui.get("description") == "cleanup" and ui.get("timeout") == 5000, str(ui))
check("rewrite: original rm text is gone", new and " rm " not in " " + new + " ", new)
code, out, err = run(f"rm {PRJ}/zz-proj/build/x")
check("rewrite: no -Recurse when -r absent", code == 0 and '" -Recurse' not in out and " -Recurse " not in json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"], out[:200])
code, out, err = run(f"rm {PRJ}/zz-proj/a/*.tmp")
check("rewrite: glob token kept for the executor", code == 0 and f'"{PRJ}/zz-proj/a/*.tmp"' in json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"], out[:200])


# ---- end-to-end shape: execute the command the guard PRODUCES (dry run), exactly as the Bash tool would run it ----
probe = pathlib.Path(FIX) / "_rm_routing_probe"
try:
    probe.mkdir(parents=True, exist_ok=True)
    (probe / "x.txt").write_text("probe"); (probe / "d").mkdir(exist_ok=True); (probe / "d" / "y.tmp").write_text("probe2")
    for label, cmd, expect_in in (
        ("single file", f"rm {FIX}/_rm_routing_probe/x.txt", "WOULD QUARANTINE"),
        ("directory with -r", f"rm -r {FIX}/_rm_routing_probe/d", "WOULD QUARANTINE"),
        ("glob", f"rm {FIX}/_rm_routing_probe/d/*.tmp", "WOULD QUARANTINE"),
    ):
        code, out, err = run(cmd)
        new = json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]
        dry = new.replace(EXE + '"', EXE + '" -DryRun', 1)
        r = subprocess.run(dry, shell=True, capture_output=True, text=True)
        check(f"e2e dry run: {label}", r.returncode == 0 and expect_in in r.stdout, f"rc={r.returncode} out={r.stdout[:150]!r} err={r.stderr[:150]!r}")
    check("e2e dry run changed nothing", (probe / "x.txt").exists() and (probe / "d" / "y.tmp").exists())
finally:
    import shutil as _sh; _sh.rmtree(probe, ignore_errors=True)

# ---- scope ----
for label, agent in (("main thread", None), ("other agent", "repo-scout")):
    code, out, err = run("rm -rf /tmp/x", agent=agent)
    check(f"{label}: guard does not apply", code == 0 and out.strip() == "", f"{code} {out[:80]}")

# ---- fail closed for the runner on an internal error, fail open otherwise ----
import os, shutil, tempfile
tmp = pathlib.Path(tempfile.mkdtemp())
try:
    shutil.copy(HOOK, tmp / HOOK.name)          # a copy WITHOUT safe-rm-lib / policy next to it -> internal error in the rm branch
    # the adapter (run.sh) and both twins must travel together: the adapter routes to whichever twin the machine uses
    for sib in (HOOK.with_suffix('.sh'), HOOK.parent / 'lib.sh', HOOK.parent / 'run.sh'):
        if sib.exists():
            shutil.copy(sib, tmp / sib.name)
    p = run_capability(tmp / HOOK.name,
                       input=json.dumps({"tool_name": "Bash", "agent_type": AGENT, "tool_input": {"command": f"rm {PRJ}/zz-proj/a/b"}}), capture_output=True, text=True)
    check("runner: internal error fails CLOSED", p.returncode == 2 and "fails closed" in p.stderr, f"{p.returncode} {p.stderr[:160]}")
    p = run_capability(tmp / HOOK.name,
                       input=json.dumps({"tool_name": "Bash", "agent_type": "repo-scout", "tool_input": {"command": f"rm {PRJ}/zz-proj/a/b"}}), capture_output=True, text=True)
    check("other agent: unaffected by that error", p.returncode == 0, f"{p.returncode}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
code, out, err = run_capability(HOOK, input="not json", capture_output=True, text=True).returncode, "", ""
check("malformed input fails open (agent unknown)", code == 0, str(code))

n = len(results)
print(f"\n{sum(results)}/{n} passed")
sys.exit(0 if all(results) else 1)
