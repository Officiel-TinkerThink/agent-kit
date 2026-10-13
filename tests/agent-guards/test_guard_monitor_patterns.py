"""Regression tests for guard-monitor-patterns.ps1. Run: python test_guard_monitor_patterns.py"""
import sys as _sys
PWSH = 'powershell.exe' if _sys.platform == 'win32' else 'pwsh'
import json, pathlib, subprocess, sys

HOOK = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-guards' / 'scripts' / "guard-monitor-patterns.ps1"

# (name, command, run_in_background, expected_exit)
CASES = [
    ("plain tail -f", "tail -f app.log", False, 2),
    ("tail -F piped", "tail -F /var/log/x.log | grep ERROR", False, 2),
    ("tail --follow", "tail --follow app.log", False, 2),
    ("timeout-prefixed tail -f", "timeout 5 tail -f app.log", False, 2),
    ("sudo tail -F", "sudo tail -F app.log", False, 2),
    ("watch at start", "watch -n 5 kubectl get pods", False, 2),
    ("timeout-prefixed watch", "timeout 5 watch ls", False, 2),
    ("Get-Content -Wait", "Get-Content app.log -Wait", False, 2),
    ("docker compose logs -f", "docker compose logs -f api", False, 2),
    ("kubectl logs --follow", "kubectl logs --follow pod/x", False, 2),
    ("while true, no exit", "while true; do curl -s localhost:8000/health; sleep 5; done", False, 2),
    ("until false, no exit", "until false; do date; sleep 2; done", False, 2),
    ("tail -n bounded", "tail -n 20 app.log", False, 0),
    ("docker logs --tail", "docker logs --tail 50 api", False, 0),
    ("while true with break", "while true; do curl -sf localhost/h && break; sleep 1; done", False, 0),
    ("while true with timeout", "timeout 60 bash -c 'while true; do sleep 1; done'", False, 0),
    ("until condition loop", "until grep -q READY app.log; do sleep 1; done", False, 0),
    ("quoted tail -f text", 'git commit -m "use tail -f for logs"', False, 0),
    ("quoted watch text", 'grep -rn "watch " src/', False, 0),
    ("watchers directory", "ls src/watchers", False, 0),
    ("background tail -f", "tail -f app.log", True, 0),
    ("background watch", "watch -n 5 ls", True, 0),
    ("plain command", "git status --short", False, 0),
]


def run(payload: str) -> int:
    p = subprocess.run(
        [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HOOK)],
        input=payload, capture_output=True, text=True,
    )
    return p.returncode


failed = 0
for name, cmd, bg, expect in CASES:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd, "run_in_background": bg}})
    got = run(payload)
    ok = got == expect
    failed += not ok
    print(("PASS" if ok else "FAIL"), f"expect {expect} got {got}  {name}")
got = run("not json")
print(("PASS" if got == 0 else "FAIL"), f"expect 0 got {got}  malformed input fails open")
failed += got != 0
got = run(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}}))
print(("PASS" if got == 0 else "FAIL"), f"expect 0 got {got}  non-Bash tool ignored")
failed += got != 0
print(f"\n{len(CASES) + 2 - failed}/{len(CASES) + 2} passed")
sys.exit(1 if failed else 0)
