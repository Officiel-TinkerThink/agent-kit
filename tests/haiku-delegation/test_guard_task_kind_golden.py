"""guard-task-kind replays the recorded cases in cases/guard-task-kind.json through each implementation that runs here.
Every case must give the recorded exit code, stdout and stderr. The record was made from the PowerShell version and
checked byte for byte against the POSIX sh version, so the same record holds on Windows (both versions) and on Linux (sh).
Run: python test_guard_task_kind_golden.py"""
import pathlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import summary  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'plugins' / 'haiku-delegation' / 'scripts' / 'guard-task-kind'
RECORD = Path(__file__).resolve().parent / 'cases' / 'guard-task-kind.json'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


golden.replay(RECORD, SCRIPT, results, check)
print(summary(results))
sys.exit(0 if all(results) else 1)
