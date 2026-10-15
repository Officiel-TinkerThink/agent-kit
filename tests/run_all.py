"""Runs every suite under tests/ and prints one line per suite plus its time. Windows + PowerShell 5.1 + Python 3.10+.
Usage: python tests/run_all.py [-j N] [--serial]     (default: cores - 2 suites at a time, between 4 and 6; slowest suites first; --serial = one after another)"""
import argparse
import concurrent.futures
import os
import pathlib
import subprocess
import sys
import tempfile
import time

here = pathlib.Path(__file__).resolve().parent
SLOW = {'test_guard_task_kind.py': 330, 'test_subagents_init.py': 280, 'test_usage_log_task_kind.py': 270, 'test_guard_turn_budget.py': 150,
        'test_guard_monitor.py': 240, 'test_issue_report.py': 220, 'test_guard_rm_routing.py': 210, 'test_guard_browser.py': 175,
        'test_safe_rm.py': 130, 'test_guard_secret_leak_sh.py': 125, 'test_guard_secret_leak.py': 120}


def run_suite(f):
    # Tests must never write hook errors or audit lines into the user's real agent-kit data folder: every suite gets its own
    # throwaway one (a suite that needs a specific folder sets AGENT_KIT_DATA itself and wins).
    env = dict(os.environ, AGENT_KIT_DATA=tempfile.mkdtemp(prefix='kit-tests-'))
    t0 = time.time()
    p = subprocess.run([sys.executable, '-X', 'utf8', str(f)], capture_output=True, text=True, timeout=1500, env=env)
    last = (p.stdout.strip().splitlines() or ['(no output)'])[-1]
    return f, p.returncode, last, time.time() - t0, p.stdout, p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', type=int, default=0, help='suites to run at the same time (default: cores - 2, between 4 and 6)')
    ap.add_argument('--serial', action='store_true')
    a = ap.parse_args()
    if a.j <= 0:
        a.j = min(6, max(4, (os.cpu_count() or 4) - 2))   # more workers did not help on Windows: process starts (PowerShell) are the limit, not the cores
    # the slowest suites start first so that none of them is left running alone at the end (names and rough seconds from a real run; a new suite counts as quick)
    suites = sorted(here.glob('*/test_*.py'), key=lambda f: (-SLOW.get(f.name, 0), str(f)))
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1 if a.serial else max(1, a.j)) as ex:
        results = list(ex.map(run_suite, suites))
    bad = 0
    for f, rc, last, secs, out, err in results:
        print('%-62s %-22s %5.0fs' % (f.relative_to(here), last, secs))
        if rc != 0:
            bad += 1
            for line in [x for x in out.splitlines() if x.startswith('FAIL')][:10] + err.strip().splitlines()[-5:]:
                print('    ' + line[:240])
    print('ALL PASSED' if not bad else '%d suite(s) FAILED' % bad, '(%.0fs total, %d at a time)' % (time.time() - t0, 1 if a.serial else a.j))
    sys.exit(1 if bad else 0)


main()
