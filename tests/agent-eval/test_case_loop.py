"""Tests for the failure-to-benchmark loop: bench/browser-agent/from_annotation.py, the case loader in bench.py, and the snapshot route in server.py.
Run: python test_case_loop.py   (no browser and no model calls)"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BENCH = pathlib.Path(__file__).resolve().parents[2] / 'bench' / 'browser-agent'
results = []


def check(name, passed, extra=''):
    results.append(bool(passed))
    print(('PASS' if passed else 'FAIL'), name, '' if passed else extra)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def setup():
    root = pathlib.Path(tempfile.mkdtemp(prefix='caseloop_')).resolve()
    kit, cases = root / 'kit', root / 'cases'
    (kit / 'eval').mkdir(parents=True)
    anns = [
        {'annotation_id': 'ann-1', 'agent_type': 'haiku-delegation:browser-explorer', 'outcome': 'missed', 'code': 'omission', 'summary': 'did not read the figure inside the frame'},
        {'annotation_id': 'ann-op', 'agent_type': 'haiku-delegation:browser-operator', 'outcome': 'wrong', 'code': 'other', 'summary': 'operator case'},
    ]
    (kit / 'eval' / 'annotations.jsonl').write_text('\n'.join(json.dumps(a) for a in anns) + '\n', encoding='utf-8')
    page = root / 'saved.html'
    page.write_text('<html><head><script src="https://cdn.example.com/x.js"></script><link href="//cdn.example.com/a.css" rel="stylesheet"></head>'
                    '<body style="background:url(https://cdn.example.com/bg.png)"><p>Quarterly revenue: 12,480 EUR.</p><img src="https://cdn.example.com/i.png"></body></html>', encoding='utf-8')
    return root, kit, cases, page


def make(env, *args):
    return subprocess.run([sys.executable, str(BENCH / 'from_annotation.py'), *args], capture_output=True, text=True, env=env)


def main():
    root, kit, cases, page = setup()
    env = dict(os.environ, AGENT_KIT_DATA=str(kit), BENCH_CASES_DIR=str(cases))
    base = ['--annotation', 'ann-1', '--html', str(page), '--question', 'Report the quarterly revenue figure.']

    r = make(env, *base, '--expect', '12480')
    check('refuses without --confirm-no-sensitive-data', r.returncode != 0 and 'REFUSED' in r.stderr and not list(cases.glob('C-*.json')), r.stderr)
    r = make(env, *base, '--confirm-no-sensitive-data')
    check('refuses a case that cannot fail (no expectation)', r.returncode != 0 and 'cannot fail' in r.stderr, r.stderr)
    r = make(env, '--annotation', 'ann-missing', '--html', str(page), '--question', 'q', '--expect', 'x', '--confirm-no-sensitive-data')
    check('refuses an unknown annotation id', r.returncode != 0 and 'not found' in r.stderr, r.stderr)
    r = make(env, '--annotation', 'ann-op', '--html', str(page), '--question', 'q', '--expect', 'x', '--confirm-no-sensitive-data')
    check('refuses an operator annotation', r.returncode != 0 and 'operator' in r.stderr, r.stderr)
    secret = root / 'secret.html'
    secret.write_text('<p>key sk-abcdefghijklmnopqrstuvwxyz123456</p>', encoding='utf-8')
    r = make(env, '--annotation', 'ann-1', '--html', str(secret), '--question', 'q', '--expect', 'x', '--confirm-no-sensitive-data')
    check('refuses a page with token-shaped text', r.returncode != 0 and 'token- or key-shaped' in r.stderr, r.stderr)

    r = make(env, *base, '--expect', '12480', '--forbid', '99,999', '--slug', 'iframe', '--confirm-no-sensitive-data')
    files = sorted(cases.glob('C-*.json'))
    check('creates a case', r.returncode == 0 and len(files) == 1 and r.stdout.startswith('CREATED C-iframe-'), r.stdout + r.stderr)
    spec = json.loads(files[0].read_text(encoding='utf-8')) if files else {}
    cid = spec.get('id', '')
    check('case file carries expectations and annotation link', spec.get('expect_all') == ['12480'] and spec.get('forbid') == ['99,999'] and spec.get('annotation', {}).get('id') == 'ann-1' and spec.get('external_refs_removed', 0) >= 3, str(spec))
    html = (cases / 'pages' / f'{cid}.html').read_text(encoding='utf-8') if cid else ''
    check('snapshot keeps the content, drops external references', '12,480' in html and 'cdn.example.com' not in html, html)

    # bench.py loads it as a task and scores answers
    code = ("import sys; sys.path.insert(0, %r); import bench; sc = bench.BASE_Q[%r][1]; p = bench.BASE_Q[%r][0]; "
            "print(bench.CASE_TASKS); print('/case/' + %r + '.html' in p); "
            "print(sc('The quarterly revenue is 12,480 EUR.', [])[0]); print(sc('It is 9,000.', [])[0]); print(sc('12480 but also 99,999', [])[0])") % (str(BENCH), cid, cid, cid)
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
    lines = r.stdout.split('\n')
    check('bench.py loads the case as a task', cid in lines[0] and lines[1] == 'True', r.stdout + r.stderr)
    check('scorer: correct answer passes (comma-insensitive)', lines[2] == 'True', r.stdout)
    check('scorer: wrong answer fails', lines[3] == 'False', r.stdout)
    check('scorer: forbidden text fails', lines[4] == 'False', r.stdout)

    r = subprocess.run([sys.executable, str(BENCH / 'bench.py'), 'run', '--cond', 'explorer-haiku-low-v5', '--tasks', 'no-such-task'], capture_output=True, text=True, env=env, cwd=str(BENCH))
    check('bench.py rejects an unknown task id before running anything', r.returncode != 0 and 'unknown task id' in (r.stderr + r.stdout), r.stderr + r.stdout)

    # server serves the snapshot and only that
    port = free_port()
    srv = subprocess.Popen([sys.executable, str(BENCH / 'server.py'), str(port), str(root / 'server-log.jsonl')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/orders.html', timeout=1)
                break
            except OSError:
                time.sleep(0.2)

        def get(path):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=3) as resp:
                    return resp.status, resp.read().decode('utf-8', 'replace')
            except urllib.error.HTTPError as e:
                return e.code, ''
        st, body = get(f'/case/{cid}.html')
        check('server serves the snapshot', st == 200 and '12,480' in body, f'{st} {body[:80]}')
        check('server: unknown case is 404', get('/case/C-nope.html')[0] == 404)
        check('server: path traversal is 404', get('/case/C-..%2f..%2fserver.py')[0] == 404 and get('/case/../server.py')[0] == 404)
        check('server: existing pages unaffected', get('/orders.html')[0] == 200)
    finally:
        srv.terminate()

    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
