"""Usage log (SubagentStop hook): a single API call whose prompt (input + cache write + cache read) is above 100000 tokens is priced at the higher tier (input side x5),
flagged `context_over_100k` (warn) and the biggest prompt of the run is recorded as `peak_context`. A prompt of exactly 100000 is still the normal tier.
The recorded cases (cases/usage-cost-tier.json) hold the cost, peak and flags that were checked against the price formula when they were recorded; they are
replayed through each implementation that runs here (see tests/golden.py). Run: python test_usage_cost_tier.py   (temp data folder)"""
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


golden.replay(CASES / 'usage-cost-tier.json', SCRIPTS / 'subagent-usage-log', results, check)
print(summary(results))
sys.exit(0 if all(results) else 1)
