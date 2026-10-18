"""guard-agent-model replays the recorded cases in cases/guard-agent-model.json through each implementation that runs here.
Each case must give the recorded exit code, stdout and stderr (see tests/golden.py). Run: python test_guard_agent_model_golden.py"""
import pathlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import summary  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'plugins' / 'haiku-delegation' / 'scripts' / 'guard-agent-model'
RECORD = Path(__file__).resolve().parent / 'cases' / 'guard-agent-model.json'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


golden.replay(RECORD, SCRIPT, results, check)
print(summary(results))
sys.exit(0 if all(results) else 1)
