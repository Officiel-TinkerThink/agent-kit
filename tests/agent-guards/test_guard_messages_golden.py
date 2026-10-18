"""check-bulk-read and guard-env-files replay their recorded cases (cases/*.json) through each implementation that runs here.
Each case must give the recorded exit code, stdout and stderr, and the files the run left behind (see tests/golden.py).
Run: python test_guard_messages_golden.py"""
import pathlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import summary  # noqa: E402

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-guards' / 'scripts'
CASES = Path(__file__).resolve().parent / 'cases'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


golden.replay(CASES / 'check-bulk-read.json', SCRIPTS / 'check-bulk-read', results, check)
golden.replay(CASES / 'guard-env-files.json', SCRIPTS / 'guard-env-files', results, check)
print(summary(results))
sys.exit(0 if all(results) else 1)
