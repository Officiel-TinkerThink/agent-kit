"""bench/cases: the case format, the privacy scan, the scorer, capture_case.py and run_cases.py. No model calls (a stub stands in for `claude`).
Run: python test_bench_cases.py   (temp folders only)"""
import copy
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCH = ROOT / 'bench' / 'cases'
sys.path.insert(0, str(BENCH))
TMP = pathlib.Path(tempfile.mkdtemp(prefix='benchcases_'))
os.environ['BENCH_CASES_DIR'] = str(TMP / 'cases')   # before casefmt is imported: nothing here may write into the real cases folder
import casefmt  # noqa: E402

results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


GOOD = {
    'schema': 'bench-case/1', 'id': 'BC-code-explorer-demo-case', 'agent': 'code-explorer', 'title': 'Demo', 'found_in': '0.2.0', 'status': 'open',
    'origin': {'type': 'annotation', 'annotation_id': 'ann-20260101T000000000000-abcdef'},
    'failure': {'code': 'omission', 'rule_broken': 'List every file.', 'symptom': 'Listed 3 of 5 files.'},
    'prompt': 'List the files in this folder.', 'fixture': {'files': {'a.txt': 'one\n', 'sub/b.txt': 'two\n'}},
    'checks': {'expect_all': ['a.txt', 'b.txt']},
}


def variant(**kw):
    c = copy.deepcopy(GOOD)
    for k, v in kw.items():
        if v is None:
            c.pop(k, None)
        else:
            c[k] = v
    return c


def problems(c):
    return ' | '.join(casefmt.validate(c))


def run(cmd, env=None, cwd=None):
    e = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, *cmd], capture_output=True, text=True, timeout=120, env=e, cwd=cwd)


def main():
    # 1. format
    check('a well-formed case has no problems', not casefmt.validate(GOOD), problems(GOOD))
    check('loader bookkeeping keys (a local path) are not scanned', not casefmt.validate(dict(GOOD, _file='C:' + chr(92) + 'Users' + chr(92) + 'jdoe' + chr(92) + 'x.json')))
    for label, c, needle in (
        ('wrong schema', variant(schema='x/1'), 'schema'),
        ('bad id', variant(id='demo'), 'id must'),
        ('unknown agent', variant(agent='no-such-agent'), 'not an agent'),
        ('no prompt', variant(prompt=''), 'prompt is required'),
        ('bad version', variant(found_in='v2'), 'found_in'),
        ('bad status', variant(status='done'), 'status'),
        ('fixed without fixed_in', variant(status='fixed'), 'fixed_in'),
        ('origin annotation without id', variant(origin={'type': 'annotation'}), 'annotation_id'),
        ('unknown failure code', variant(failure={'code': 'x', 'rule_broken': 'r', 'symptom': 's'}), 'failure.code'),
        ('missing symptom', variant(failure={'code': 'omission', 'rule_broken': 'r', 'symptom': ''}), 'symptom'),
        ('check that cannot fail', variant(checks={}), 'cannot fail'),
        ('unknown check', variant(checks={'expect_all': ['a'], 'magic': 1}), 'unknown checks'),
        ('bad regular expression', variant(checks={'require_regex': ['(']}), 'regular expression'),
        ('min_turns out of range', variant(checks={'min_turns': 99}), 'min_turns'),
        ('absolute fixture path', variant(fixture={'files': {'/etc/x': 'a'}}), 'safe relative path'),
        ('fixture path with ..', variant(fixture={'files': {'a/../../x': 'a'}}), 'safe relative path'),
        ('binary-looking fixture value', variant(fixture={'files': {'a': 5}}), 'must be text'),
        ('oversized fixture', variant(fixture={'files': {'a.txt': 'x' * 25000}}), 'larger than'),
        ('too many fixture files', variant(fixture={'files': {f'f{i}.txt': 'x' for i in range(25)}}), 'more than'),
        ('bad allow entry', variant(allow=['Bash(a;b)\nrm']), 'allow'),
    ):
        pr = problems(c)
        check(f'rejects: {label}', needle in pr, pr)
    check('an empty fixture is allowed', not casefmt.validate(variant(fixture={'files': {}})))
    # 2. privacy scan (a case lives on a public branch)
    for label, text in (('a GitHub token', 'ghp_' + 'a' * 24), ('an OpenAI-style key', 'sk-' + 'b' * 24), ('a private key header', '-----BEGIN RSA PRIVATE KEY-----'),
                        ('a URL password', 'https://user:hunter2hunter2@example.com/x'), ('a key=value secret', 'password = "abcdefghijkl1234"'),
                        ('a Windows home path', 'C:' + chr(92) + 'Users' + chr(92) + 'jdoe' + chr(92) + 'x'), ('a Linux home path', '/home/alice/x'), ('an e-mail address', 'a.b@corp.com')):
        for where, c in (('in the fixture', variant(fixture={'files': {'a.txt': text}})), ('in the prompt', variant(prompt=text)), ('in the symptom', variant(failure={'code': 'omission', 'rule_broken': 'r', 'symptom': text}))):
            pr = problems(c)
            check(f'privacy scan finds {label} {where}', 'replace it with synthetic text' in pr, pr)
    check('the privacy message never repeats the text', 'ghp_' not in problems(variant(prompt='ghp_' + 'a' * 24)))
    # 3. scorer
    c = variant(checks={'expect_all': ['3/3 passed'], 'forbid': ['BLOCKED'], 'require_regex': ['exit[= ]0'], 'min_turns': 2})
    check('scorer: a good answer passes', casefmt.score(c, '3/3 passed exit=0', 3)[0])
    check('scorer: a missing expectation fails', not casefmt.score(c, 'exit=0', 3)[0])
    check('scorer: a forbidden text fails', not casefmt.score(c, '3/3 passed exit=0 BLOCKED', 3)[0])
    check('scorer: a missing regex match fails', not casefmt.score(c, '3/3 passed', 3)[0])
    check('scorer: too few turns fails (the agent must act)', not casefmt.score(c, '3/3 passed exit=0', 1)[0])
    check('scorer: unknown turns fail min_turns', not casefmt.score(c, '3/3 passed exit=0', None)[0])
    check('scorer: expect_any needs one hit', casefmt.score(variant(checks={'expect_any': ['a', 'b']}), 'xbx')[0] and not casefmt.score(variant(checks={'expect_any': ['a', 'b']}), 'xyz')[0])
    check('scorer: forbid_regex', not casefmt.score(variant(checks={'forbid_regex': ['exit=[0-9]']}), 'exit=0')[0] and casefmt.score(variant(checks={'forbid_regex': ['exit=[0-9]']}), 'nothing')[0])

    # 4. the shipped cases
    os.environ.pop('BENCH_CASES_DIR', None)
    shipped = casefmt.load_dir(BENCH / 'cases')
    os.environ['BENCH_CASES_DIR'] = str(TMP / 'cases')
    check('the shipped cases folder has at least the two seed cases', len(shipped) >= 2, str(list(shipped)))
    for cid, c in shipped.items():
        f = pathlib.Path(c['_file'])
        check(f'shipped case {cid}: valid, file name and folder match its id and agent', not casefmt.validate(c) and f.stem == cid and f.parent.name == c['agent'], problems(c))
    seed = shipped.get('BC-verification-runner-blocked-no-run')
    if seed:
        bad = 'BLOCKED: no commands run'
        check('seed case 1 fails the answer that was the real failure', not casefmt.score(seed, bad, 1)[0])
        good = 'exit=0 3/3 passed log: C:/x/.kit/verification-logs/check-1.log'
        check('seed case 1 passes a correct report', casefmt.score(seed, good, 4)[0], str(casefmt.score(seed, good, 4)))
    seed = shipped.get('BC-verification-runner-no-kit-data-reply')
    if seed:
        check('seed case 2 fails the generic BLOCKED reply', not casefmt.score(seed, 'BLOCKED: no commands run', 1)[0])
        check('seed case 2 fails a run that went ahead without KIT_DATA', not casefmt.score(seed, 'exit=0 3/3 passed', 3)[0])
        check('seed case 2 passes the sentence the agent rule prescribes', casefmt.score(seed, 'KIT_DATA missing; start-up hook failed (see hook-errors.log in the agent-kit data folder)', 1)[0])
    v = run([str(BENCH / 'run_cases.py'), 'validate'])
    check('run_cases.py validate passes on the shipped folder', v.returncode == 0 and 'valid' in v.stdout, v.stdout + v.stderr)

    # 5. capture_case.py (annotation -> case), in a temp data folder and a temp cases folder
    kit = TMP / 'kit'
    (kit / 'eval').mkdir(parents=True)
    ann = lambda i, v: json.dumps({'annotation_id': i, 'agent_type': 'haiku-delegation:code-explorer', 'code': 'omission', 'summary': 'Listed 3 of 5 files.', 'verified': v})  # noqa: E731
    (kit / 'eval' / 'annotations.jsonl').write_text(ann('ann-20260101T000000000000-good01', 'yes') + '\n' + ann('ann-20260101T000000000000-bad002', 'no') + '\n', encoding='utf-8')
    fx = TMP / 'fx'
    fx.mkdir()
    (fx / 'a.txt').write_text('one\n', encoding='utf-8')
    (fx / 'sub').mkdir()
    (fx / 'sub' / 'b.txt').write_text('two\n', encoding='utf-8')
    pf = TMP / 'prompt.txt'
    pf.write_text('List the files in this folder.\n', encoding='utf-8')
    base = [str(BENCH / 'capture_case.py'), '--annotation', 'ann-20260101T000000000000-good01', '--slug', 'list-files', '--prompt-file', str(pf), '--fixture-dir', str(fx),
            '--rule-broken', 'List every file.', '--expect-all', 'a.txt', '--expect-all', 'b.txt']
    env = {'AGENT_KIT_DATA': str(kit)}
    r = run(base, env)
    check('capture refuses without --confirm-no-sensitive-data and writes nothing', r.returncode == 2 and 'REFUSED' in r.stderr and not (TMP / 'cases').exists(), r.stderr)
    r = run(base[:2] + ['ann-20260101T000000000000-nope99'] + base[3:] + ['--confirm-no-sensitive-data'], env)
    check('capture refuses an unknown annotation', r.returncode == 2 and 'not found' in r.stderr, r.stderr)
    r = run(base[:2] + ['ann-20260101T000000000000-bad002'] + base[3:] + ['--confirm-no-sensitive-data'], env)
    check('capture refuses an annotation the annotator could not confirm', r.returncode == 2 and 'verified: no' in r.stderr, r.stderr)
    r = run([x for x in base if x not in ('--expect-all', 'a.txt', 'b.txt')] + ['--confirm-no-sensitive-data'], env)
    check('capture refuses a case whose checks cannot fail', r.returncode == 2 and 'cannot fail' in r.stderr, r.stderr)
    (fx / 'leak.txt').write_text('token = "abcdefghijkl1234567"\n', encoding='utf-8')
    r = run(base + ['--confirm-no-sensitive-data'], env)
    check('capture refuses a fixture with a secret and writes nothing', r.returncode == 2 and 'secret-shaped' in r.stderr and not (TMP / 'cases').exists(), r.stderr)
    (fx / 'leak.txt').unlink()
    r = run(base + ['--confirm-no-sensitive-data', '--allow', 'Read'], dict(env, BENCH_CASES_DIR=str(TMP / 'cases')))
    out = TMP / 'cases' / 'code-explorer' / 'BC-code-explorer-list-files.json'
    check('capture writes the case file for a good request', r.returncode == 0 and out.exists(), r.stdout + r.stderr)
    cj = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    check('the case carries the annotation id, the failure code, the fixture and the version', cj.get('origin', {}).get('annotation_id') == 'ann-20260101T000000000000-good01'
          and cj.get('failure', {}).get('code') == 'omission' and set(cj.get('fixture', {}).get('files', {})) == {'a.txt', 'sub/b.txt'} and cj.get('found_in') and cj.get('allow') == ['Read'], str(cj)[:300])
    r = run(base + ['--confirm-no-sensitive-data'], dict(env, BENCH_CASES_DIR=str(TMP / 'cases')))
    check('capture never overwrites an existing case', r.returncode == 2 and 'exists' in r.stderr, r.stderr)

    # 6. run_cases.py with a stub for claude
    stub = TMP / 'stub_claude.py'
    stub.write_text('import json, os, pathlib, sys\n'
                    'a = sys.argv[1:]\n'
                    'rec = {"args": a, "files": sorted(str(p.relative_to(".")).replace(chr(92), "/") for p in pathlib.Path(".").rglob("*") if p.is_file())}\n'
                    'open(os.environ["STUB_LOG"], "a", encoding="utf-8").write(json.dumps(rec) + "\\n")\n'
                    'print(json.dumps({"result": os.environ.get("STUB_ANSWER", ""), "num_turns": int(os.environ.get("STUB_TURNS", "3")), "total_cost_usd": 0.01, "is_error": False}))\n', encoding='utf-8')
    casedir = TMP / 'cases'
    log = TMP / 'stub.log'
    renv = {'BENCH_CASES_DIR': str(casedir), 'BENCH_CLAUDE': str(stub), 'STUB_LOG': str(log), 'STUB_ANSWER': 'a.txt b.txt'}
    results_file = BENCH / 'results' / 'runs.jsonl'
    had = results_file.exists()
    before = results_file.read_text(encoding='utf-8') if had else ''
    r = run([str(BENCH / 'run_cases.py'), 'run', '--reps', '2', '--workers', '1'], renv)
    check('run: a correct stub answer passes both reps', r.returncode == 0 and '2/2 passed' in r.stdout, r.stdout + r.stderr)
    calls = [json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()]
    a0 = calls[0]['args'] if calls else []
    check('run: the agent runs in a folder holding the fixture files', calls and {'a.txt', 'sub/b.txt'} <= set(calls[0]['files']), str(calls[:1]))
    spec = json.loads(pathlib.Path(a0[a0.index('--agents') + 1]).read_text(encoding='utf-8')) if a0 and pathlib.Path(a0[a0.index('--agents') + 1]).exists() else None
    check('run: the agent definition is built from the repo file (tools, model, name)', '--agent' in a0 and a0[a0.index('--agent') + 1] == 'code-explorer' and a0[a0.index('--model') + 1] == 'claude-haiku-5-5', str(a0)[:300])
    check('run: only the tools the case allows are passed', a0 and a0[a0.index('--allowedTools') + 1] == 'Read' and a0[a0.index('--allowedTools') + 2] == '--output-format', str(a0)[:400])
    check('run: results are appended to results/runs.jsonl with the kit version', results_file.exists() and '"kit_version"' in results_file.read_text(encoding='utf-8').splitlines()[-1])
    renv['STUB_ANSWER'] = 'nothing useful'
    r = run([str(BENCH / 'run_cases.py'), 'run', '--reps', '1'], renv)
    check('run: a wrong stub answer fails and the notes say why', r.returncode == 0 and 'FAIL' in r.stdout and 'missing: a.txt' in r.stdout, r.stdout + r.stderr)
    r = run([str(BENCH / 'run_cases.py'), 'run', '--cases', 'BC-nope-nope'], renv)
    check('run: an unknown case id is rejected', r.returncode == 2 and 'unknown case' in r.stdout, r.stdout)
    r = run([str(BENCH / 'run_cases.py'), 'run', '--reps', '3', '--budget', '0.015', '--workers', '1'], renv)
    check('run: the budget stops further runs and says so', 'skipped' in r.stdout, r.stdout)
    r = run([str(BENCH / 'run_cases.py'), 'report'], renv)
    check('report: pass rate per case and kit version', 'BC-code-explorer-list-files' in r.stdout and '/' in r.stdout, r.stdout)
    bad = json.loads(out.read_text(encoding='utf-8'))
    bad['checks'] = {}
    out.write_text(json.dumps(bad), encoding='utf-8')
    r = run([str(BENCH / 'run_cases.py'), 'run'], renv)
    check('run: refuses an invalid case and runs nothing', r.returncode == 2 and 'REFUSED' in r.stdout, r.stdout)
    # tidy the run log this test wrote into the checkout
    if had:
        results_file.write_text(before, encoding='utf-8')
    elif results_file.exists():
        results_file.unlink()
    gi = (BENCH / '.gitignore').read_text(encoding='utf-8')
    check('results and caches are git-ignored', 'results/' in gi)
    print(f'{sum(results)}/{len(results)} passed')
    import shutil
    shutil.rmtree(TMP, ignore_errors=True) if TMP.name.startswith('benchcases_') and TMP.parent == pathlib.Path(tempfile.gettempdir()) else None
    sys.exit(0 if all(results) else 1)


main()
