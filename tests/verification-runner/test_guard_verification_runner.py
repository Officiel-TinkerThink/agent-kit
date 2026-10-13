"""Regression tests for guard-verification-runner.ps1. Run: python test_guard_verification_runner.py"""
import json, pathlib, subprocess, sys

HOOK = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'verification-runner' / 'scripts' / "guard-verification-runner.ps1"

import os as _os, tempfile as _tf, json as _json
_KIT = pathlib.Path(_tf.mkdtemp(prefix='kit_')).resolve()   # long (non 8.3) path: the guards refuse '~' names
(_KIT / 'verification-logs').mkdir(parents=True)
(_KIT / 'verification-fixtures').mkdir()
(_KIT / 'safe-rm-policy.json').write_text(_json.dumps({
    'version': 1, 'quarantineRoot': '${DATA}/quarantine', 'auditFile': '${DATA}/verification-logs/_deletions.jsonl',
    'allowedRoots': [{'path': '${DATA}/verification-logs', 'minDepth': 1, 'allowGlob': False, 'maxItems': 1},
                     {'path': '${DATA}/verification-fixtures', 'minDepth': 1, 'allowGlob': True, 'maxItems': 20},
                     {'path': 'D:/core/projects', 'minDepth': 2, 'allowGlob': True, 'maxItems': 20}],
    'protectedComponents': ['.git', '.claude', '.claude-me', '.ssh', '.gnupg', '.venv', 'venv', 'quarantine', 'agent-kit'],
    'protectedNames': ['.env', '.env.*', '*.pem', '*.key', '*.pfx', 'id_rsa*', '_deletions.jsonl', '*.sqlite', '*.sqlite3', '*.db'],
    'caps': {'maxFiles': 5000, 'maxBytes': 209715200, 'maxGlobMatches': 100, 'maxTokens': 20}}), encoding='utf-8')
_os.environ['AGENT_KIT_DATA'] = str(_KIT).replace('\\', '/')
KIT_POSIX = str(_KIT).replace('\\', '/')
KIT_WIN = str(_KIT).replace('/', '\\')
LOG = KIT_POSIX + "/verification-logs"
(_KIT / "verification-logs" / "baseline-unit.log").write_text("x", encoding="utf-8")
EXISTING = "baseline-unit.log"  # created by the baseline run; must be refused as an overwrite
AGENT = "verification-runner"

ok_tail = f" > {LOG}/t-{{n}}.log 2>&1 ; echo exit=$?"

# (name, command, agent_type, expected_exit)
CASES = [
    # --- allowed ---
    ("pytest with cd", "cd D:/core/projects/example_project/backend && .venv/Scripts/python.exe -m pytest tests/api/test_x.py -q" + ok_tail.format(n=1), AGENT, 0),
    ("bare pytest", "pytest -q" + ok_tail.format(n=2), AGENT, 0),
    ("uv run pytest", "uv run pytest tests/unit -q --no-header" + ok_tail.format(n=3), AGENT, 0),
    ("python -m pytest -k expr", 'python -m pytest -k "body and not chunked" -q' + ok_tail.format(n=4), AGENT, 0),
    ("ruff check", "ruff check src" + ok_tail.format(n=5), AGENT, 0),
    ("mypy", "mypy src --strict" + ok_tail.format(n=6), AGENT, 0),
    ("npm run test", "cd D:/core/projects/x/frontend && npm run test" + ok_tail.format(n=7), AGENT, 0),
    ("npx vitest run", "npx vitest run --reporter=dot" + ok_tail.format(n=8), AGENT, 0),
    ("tsc --noEmit", "tsc --noEmit" + ok_tail.format(n=9), AGENT, 0),
    ("go test", "go test ./..." .replace("...", "...") + ok_tail.format(n=10), AGENT, 0),
    ("redirect without echo", f"pytest -q > {LOG}/t-11.log 2>&1", AGENT, 0),
    ("windows-style log path", rf"pytest -q > {KIT_WIN}\verification-logs\t-12.log 2>&1", AGENT, 0),
    ("absolute venv python", "D:/core/projects/example_project/backend/.venv/Scripts/python.exe -m pytest D:/x/fixtures/suite -q" + ok_tail.format(n=13), AGENT, 0),
    ("windows venv python path", r"cd D:\x\suite && D:\core\projects\example_project\backend\.venv\Scripts\python.exe -m pytest -q" + ok_tail.format(n=14), AGENT, 0),
    ("venv python running a script", "D:/core/projects/example_project/backend/.venv/Scripts/python.exe evil.py" + ok_tail.format(n=32), AGENT, 0),  # left to Claude Code permissions
    ("venv python -c", 'D:/core/projects/example_project/backend/.venv/Scripts/python.exe -c "print(1)"' + ok_tail.format(n=33), AGENT, 0),  # left to Claude Code permissions
    # --- commands: no allowlist of our own any more; Claude Code permissions decide, the hook stays silent (0) ---
    ("rm", "rm -rf /tmp/x", AGENT, 2),
    ("curl", "curl http://example.com", AGENT, 0),  # left to Claude Code permissions
    ("pip install", "pip install requests" + ok_tail.format(n=20), AGENT, 0),  # left to Claude Code permissions
    ("npm install", "npm install" + ok_tail.format(n=21), AGENT, 0),  # left to Claude Code permissions
    ("python -c", 'python -c "import os; os.remove(1)"' + ok_tail.format(n=22), AGENT, 0),  # left to Claude Code permissions
    ("git push", "git push origin main", AGENT, 0),  # left to Claude Code permissions
    # --- what the hook still enforces: deletes only as a bare rm line, evidence logs are new files only ---
    ("no redirect", "pytest -q", AGENT, 0),  # left to Claude Code permissions
    ("pipe to head", "pytest -q | head -50", AGENT, 0),  # left to Claude Code permissions
    ("chained rm", "pytest -q" + ok_tail.format(n=23) + " ; rm -rf x", AGENT, 2),
    ("and-chain", "pytest -q && rm -rf x" + ok_tail.format(n=24), AGENT, 2),
    ("background &", "pytest -q" + f" > {LOG}/t-25.log 2>&1 &", AGENT, 0),  # left to Claude Code permissions
    ("command substitution in args", "pytest -k $(whoami)" + ok_tail.format(n=26), AGENT, 0),  # left to Claude Code permissions
    ("backtick in args", "pytest -k `whoami`" + ok_tail.format(n=27), AGENT, 0),  # left to Claude Code permissions
    ("dollar in quoted args", 'pytest -k "a$b"' + ok_tail.format(n=28), AGENT, 0),  # left to Claude Code permissions
    ("redirect to other dir", "pytest -q > /tmp/out.log 2>&1", AGENT, 0),  # left to Claude Code permissions
    ("redirect outside via ..", f"pytest -q > {LOG}/../x.log 2>&1", AGENT, 2),
    ("append redirect", f"pytest -q >> {LOG}/t-29.log 2>&1", AGENT, 2),
    ("overwrite existing log", f"pytest -q > {LOG}/{EXISTING} 2>&1", AGENT, 2),
    ("cd then other command", "cd x && ls" + ok_tail.format(n=30), AGENT, 0),  # left to Claude Code permissions
    ("cd with substitution", "cd $(pwd) && pytest -q" + ok_tail.format(n=31), AGENT, 0),  # left to Claude Code permissions
    # --- scope ---
    ("other agent unaffected", "rm -rf x", "repo-scout", 0),
    ("main thread unaffected", "rm -rf x", None, 0),
]


def run(payload: str) -> int:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HOOK)],
        input=payload, capture_output=True, text=True,
    ).returncode


failed = 0
for name, cmd, agent, expect in CASES:
    d = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    if agent:
        d["agent_type"] = agent
    got = run(json.dumps(d))
    ok = got == expect
    failed += not ok
    print(("PASS" if ok else "FAIL"), f"expect {expect} got {got}  {name}")
got = run("not json")
print(("PASS" if got == 0 else "FAIL"), f"expect 0 got {got}  malformed input fails open")
failed += got != 0
n = len(CASES) + 1
print(f"\n{n - failed}/{n} passed")
sys.exit(1 if failed else 0)
