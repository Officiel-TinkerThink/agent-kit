"""guard-task-kind replays the recorded cases in cases/guard-task-kind.json through each implementation that runs here.
Every case must give the recorded exit code, stdout and stderr. The record was made from the PowerShell version and
checked byte for byte against the POSIX sh version, so the same record holds on Windows (both versions) and on Linux (sh).
Run: python test_guard_task_kind_golden.py"""
import json
import os
import pathlib
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capability import capability_variants, summary  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'haiku-delegation' / 'scripts'
CASES_FILE = Path(__file__).resolve().parent / 'cases' / 'guard-task-kind.json'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    ts = capability_variants(SCRIPTS / 'guard-task-kind')
    check('at least one guard version can run here', bool(ts))
    cases = json.loads(CASES_FILE.read_text(encoding='utf-8'))
    for name, cmd in ts.items():
        for case in cases:
            p = subprocess.run(cmd, input=case['stdin'], capture_output=True, text=True, timeout=120,
                               env=dict(os.environ, **case['env']))
            got = {'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
            want = {'exit': case['exit'], 'stdout': case['stdout'], 'stderr': case['stderr']}
            diff = [k for k in want if got[k] != want[k]]
            check(f"[{name}] {case['id']} matches the record", not diff,
                  f"differs in {diff}: exit {got['exit']} want {want['exit']}")


main()
print(summary(results))
sys.exit(0 if all(results) else 1)
