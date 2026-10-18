"""The merged agents (code-explorer, contracts-reader) serve several kinds of task. The usage-log hook reads the brief's `Task kind: <kind>` line and applies
the footer checks (Coverage, Reconciliation) of that kind only. The recorded cases (cases/usage-log-task-kind.json) are replayed through each implementation
that runs here (the PowerShell and the POSIX sh hook; see tests/golden.py). Run: python test_usage_log_task_kind.py   (uses a temp data folder)"""
import pathlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import summary  # noqa: E402

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-eval' / 'scripts'
CASES = Path(__file__).resolve().parent / 'cases'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


golden.replay(CASES / 'usage-log-task-kind.json', SCRIPTS / 'subagent-usage-log', results, check)
print(summary(results))
sys.exit(0 if all(results) else 1)
