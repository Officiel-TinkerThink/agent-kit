"""guard-verification-runner replays the recorded Monitor/Bash cases (cases/guard-verification-runner.json) through each
implementation that runs here. Each case must give the recorded exit code, stdout and stderr (see tests/golden.py).
Run: python test_guard_monitor_golden.py"""
import pathlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import summary  # noqa: E402

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'verification-runner' / 'scripts' / 'guard-verification-runner'
RECORD = Path(__file__).resolve().parent / 'cases' / 'guard-verification-runner.json'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


golden.replay(RECORD, SCRIPT, results, check)
print(summary(results))
sys.exit(0 if all(results) else 1)
