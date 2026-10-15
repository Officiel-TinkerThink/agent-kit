"""Run the benchmark cases (agent failures kept as repeatable tests) against the agents of this checkout, headless, on Haiku.

  python run_cases.py validate                      check every case file (schema, privacy scan, checks that can fail); no model calls
  python run_cases.py list                          one line per case
  python run_cases.py run [--cases ID,ID] [--agent NAME] [--reps 3] [--workers 2] [--budget 2.0] [--model claude-haiku-5-5]
  python run_cases.py report                        pass rate per case and per kit version, from results/runs.jsonl

A run builds a temp folder from the case's fixture, starts the agent exactly as the case says (`claude -p --agent ... --agents ...`), scores the answer with the case's
checks and appends one line to results/runs.jsonl (kept on this device; the folder is git-ignored). Compare versions by checking out another tag and running again.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casefmt  # noqa: E402

RESULTS = HERE / 'results'
RUNS = RESULTS / 'runs.jsonl'
CLAUDE = os.environ.get('BENCH_CLAUDE') or shutil.which('claude')   # BENCH_CLAUDE: tests put a stub here
LOCK = threading.Lock()
SPENT = [0.0]
RUN_CAP = 0.25


def parse_agent(path):
    text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
    parts = text.split('---\n', 2)
    if len(parts) < 3:
        raise ValueError(f'{path}: no frontmatter')
    meta = {}
    for line in parts[1].splitlines():
        m = re.match(r'^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$', line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta, parts[2].strip()


def plugin_version(agent_file):
    try:
        return json.loads((agent_file.parents[1] / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']
    except (OSError, ValueError, KeyError):
        return 'unknown'


def materialize(case, tmp):
    for rel, text in case['fixture']['files'].items():
        f = tmp / rel
        if tmp.resolve() not in f.resolve().parents:
            raise ValueError(f'fixture path escapes the sandbox: {rel}')
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding='utf-8', newline='\n')
    kit = tmp / '.kit'
    (kit / 'verification-logs').mkdir(parents=True, exist_ok=True)
    return kit


def run_one(case, rep, model, budget):
    with LOCK:
        if SPENT[0] >= budget:
            return None
    agents = casefmt.agent_names()
    af_path = agents[case['agent']]
    meta, body = parse_agent(af_path)
    tools = [t.strip() for t in meta.get('tools', 'Read, Grep, Glob').split(',') if t.strip()]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='benchcase_'))
    try:
        kit = materialize(case, tmp)
        prompt = case['prompt'].replace('{kit_data}', str(kit).replace('\\', '/'))
        spec = {case['agent']: {'description': meta.get('description', case['agent']), 'prompt': body, 'tools': tools, 'model': model, 'maxTurns': int(meta.get('maxTurns', 30))}}
        spec_file = tmp / '.agents.json'
        spec_file.write_text(json.dumps(spec), encoding='utf-8')
        allow = case.get('allow') or tools
        cmd = [*([sys.executable, CLAUDE] if CLAUDE and CLAUDE.endswith('.py') else [CLAUDE or 'claude']), '-p', prompt, '--agent', case['agent'], '--agents', str(spec_file), '--model', model, '--effort', meta.get('effort', 'low'),
               '--setting-sources', 'project', '--allowedTools', *allow, '--output-format', 'json', '--max-budget-usd', str(RUN_CAP), '--no-session-persistence']
        t0 = time.time()
        rec = {'case': case['id'], 'agent': case['agent'], 'kit_version': plugin_version(af_path), 'model': model, 'rep': rep}
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=tmp, encoding='utf-8', errors='replace')
            out, err = p.stdout.strip(), p.stderr.strip()
        except subprocess.TimeoutExpired:
            out, err = '', 'timeout 300s'
        rec['wall_s'] = round(time.time() - t0, 1)
        try:
            j = json.loads(out.splitlines()[-1])
        except (ValueError, IndexError):
            rec.update(error=(err or out)[:300], passed=False, notes=['no result from claude'], cost=0.0)
            return rec
        answer = j.get('result') or ''
        ok, notes = casefmt.score(case, answer, j.get('num_turns'))
        rec.update(passed=bool(ok), notes=notes, cost=round(j.get('total_cost_usd', 0.0), 5), turns=j.get('num_turns'), is_error=j.get('is_error'), answer=answer[:4000])
        with LOCK:
            SPENT[0] += rec['cost']
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True) if tmp.name.startswith('benchcase_') else None


def cmd_validate(_a):
    try:
        cases = casefmt.load_dir()
    except ValueError as e:
        print('FAIL', e)
        return 1
    bad = 0
    ids = {}
    for cid, c in cases.items():
        probs = casefmt.validate(c)
        f = pathlib.Path(c['_file'])
        if f.stem != c.get('id'):
            probs.append(f'file name {f.name} must be {c.get("id")}.json')
        if f.parent.name != c.get('agent'):
            probs.append(f'case sits in folder {f.parent.name} but its agent is {c.get("agent")}')
        if cid in ids:
            probs.append('duplicate id')
        ids[cid] = 1
        print(('FAIL' if probs else 'PASS'), cid, '; '.join(probs))
        bad += bool(probs)
    print(f'{len(cases) - bad}/{len(cases)} valid')
    return 1 if bad else 0


def cmd_list(_a):
    for cid, c in casefmt.load_dir().items():
        print(f"{cid}\t{c.get('agent')}\t{c.get('status')}\tfound {c.get('found_in')}\t{c.get('failure', {}).get('code')}\t{c.get('title')}")
    return 0


def cmd_run(a):
    cases = casefmt.load_dir()
    want = [x for x in (a.cases or '').split(',') if x]
    sel = [c for cid, c in cases.items() if (not want or cid in want) and (not a.agent or c.get('agent') == a.agent)]
    if want and len(sel) != len(want):
        print('unknown case id(s):', sorted(set(want) - set(cases)))
        return 2
    for c in sel:
        probs = casefmt.validate(c)
        if probs:
            print(f"REFUSED {c.get('id')}: {'; '.join(probs)}")
            return 2
    if not CLAUDE:
        print('claude is not on the PATH')
        return 2
    RESULTS.mkdir(exist_ok=True)
    jobs = [(c, r) for c in sel for r in range(1, a.reps + 1)]
    done = []

    def work(job):
        rec = run_one(job[0], job[1], a.model, a.budget)
        if rec:
            with LOCK:
                with RUNS.open('a', encoding='utf-8') as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
                done.append(rec)
                print(('PASS' if rec['passed'] else 'FAIL'), rec['case'], f"rep {rec['rep']}", f"${rec.get('cost', 0):.3f}", '; '.join(rec.get('notes') or []))
        return rec
    sem = threading.Semaphore(a.workers)

    def guarded(job):
        with sem:
            return work(job)
    ts = [threading.Thread(target=guarded, args=(j,)) for j in jobs]
    [t.start() for t in ts]
    [t.join() for t in ts]
    skipped = len(jobs) - len(done)
    print(f'{sum(r["passed"] for r in done)}/{len(done)} passed, ${SPENT[0]:.3f} spent' + (f', {skipped} run(s) skipped: budget ${a.budget} reached' if skipped else ''))
    return 0


def cmd_report(_a):
    if not RUNS.exists():
        print('no results yet: python run_cases.py run')
        return 0
    recs = [json.loads(x) for x in RUNS.read_text(encoding='utf-8').splitlines() if x.strip()]
    table = {}
    for r in recs:
        k = (r['case'], r.get('kit_version', '?'))
        t = table.setdefault(k, [0, 0])
        t[0] += bool(r.get('passed'))
        t[1] += 1
    print('case                                         kit      passed')
    for (cid, ver), (p, n) in sorted(table.items()):
        print(f'{cid:44} {ver:8} {p}/{n}')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('validate')
    sub.add_parser('list')
    sub.add_parser('report')
    r = sub.add_parser('run')
    r.add_argument('--cases', default='')
    r.add_argument('--agent', default='')
    r.add_argument('--reps', type=int, default=3)
    r.add_argument('--workers', type=int, default=2)
    r.add_argument('--budget', type=float, default=2.0)
    r.add_argument('--model', default='claude-haiku-5-5')
    a = ap.parse_args()
    sys.exit({'validate': cmd_validate, 'list': cmd_list, 'run': cmd_run, 'report': cmd_report}[a.cmd](a))


if __name__ == '__main__':
    main()
