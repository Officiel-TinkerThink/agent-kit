"""Runs every suite under tests/ and prints one line per suite plus its time. Windows + PowerShell 5.1 + Python 3.10+.
Usage: python tests/run_all.py [-j N] [--serial]     (default: 4 suites at a time; --serial = one after another)"""
import argparse
import concurrent.futures
import os
import pathlib
import subprocess
import sys
import tempfile
import time

here = pathlib.Path(__file__).resolve().parent


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
    ap.add_argument('-j', type=int, default=4, help='suites to run at the same time')
    ap.add_argument('--serial', action='store_true')
    a = ap.parse_args()
    suites = sorted(here.glob('*/test_*.py'))
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
