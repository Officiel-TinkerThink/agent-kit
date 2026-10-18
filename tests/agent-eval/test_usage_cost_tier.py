"""Usage log (SubagentStop hook): a single API call whose prompt (input + cache write + cache read) is above 100000 tokens is priced at the higher tier (input side x5),
flagged `context_over_100k` (warn) and the biggest prompt of the run is recorded as `peak_context`. A prompt of exactly 100000 is still the normal tier. Runs the PowerShell and the POSIX sh
version (whichever exist here) on the same synthetic transcripts and requires the same cost, flag and peak. Run: python test_usage_cost_tier.py   (temp log and kit data folder)"""
import concurrent.futures
import json
import os
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capability import capability_variants, summary  # noqa: E402
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-eval' / 'scripts'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='tier_'))
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    return capability_variants(SCRIPTS / 'subagent-usage-log')


def price(u):
    """the expected estimate for one call: (input, cache write, cache read, output) in tokens"""
    i, cw, cr, o = u
    p = i + cw + cr
    if p > 100000:
        return (i * 0.50 + cw * 0.625 + cr * 0.05 + o * 0.50) / 1e6
    return (i * 0.10 + cw * 0.125 + cr * 0.01 + o * 0.50) / 1e6


def run(cmd, calls, tag):
    rows = [{'type': 'user', 'timestamp': '2026-10-12T10:00:00.000Z', 'message': {'role': 'user', 'content': 'do the task'}}]
    for n, (i, cw, cr, o) in enumerate(calls, 1):
        use = {'input_tokens': i, 'output_tokens': o, 'cache_read_input_tokens': cr, 'cache_creation_input_tokens': cw}
        content = [{'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': 'Coverage: read 1 file.'}}] if n == len(calls) else [{'type': 'thinking', 'thinking': ''}]
        rows.append({'type': 'assistant', 'timestamp': '2026-10-12T10:00:%02d.000Z' % n, 'uuid': 'u%d' % n, 'message': {'id': 'm%d' % n, 'model': 'claude-haiku-5-5', 'usage': use, 'content': content}})
    tp = TMP / f'{tag}.jsonl'
    tp.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    inp = TMP / f'{tag}.in.json'
    inp.write_text(json.dumps({'session_id': 's', 'agent_id': 'agent-' + tag, 'agent_type': 'code-explorer', 'effort': {'level': 'low'}, 'cwd': str(TMP), 'agent_transcript_path': str(tp)}), encoding='utf-8')
    log = TMP / f'{tag}.log.jsonl'
    env = dict(os.environ, AGENT_USAGE_LOG=str(log), AGENT_KIT_DATA=str(TMP / 'kit'))
    subprocess.run(cmd + ['-SelfTestInput', str(inp)], env=env, check=True, capture_output=True, timeout=120)
    return json.loads(log.read_text(encoding='utf-8').splitlines()[-1])


CASES = [
    ('small calls only', [(2, 500, 1000, 100), (3, 0, 2000, 50)], 0),
    ('one call above 100k', [(2, 500, 1000, 100), (10, 0, 150000, 300)], 1),
    ('a prompt of exactly 100000 is the normal tier', [(0, 0, 100000, 200)], 0),
    ('a prompt of 100001 is the higher tier', [(1, 0, 100000, 200)], 1),
    ('two big calls', [(5, 20000, 120000, 400), (5, 0, 180000, 500), (2, 100, 900, 10)], 2),
]


def main():
    ts = tools()
    check('at least one version can run here', bool(ts))
    got = {}
    jobs = [(tool, cmd, n) for tool, cmd in ts.items() for n in range(len(CASES))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:   # one run of the hook takes seconds on Windows: run them side by side
        recs = dict(zip([(t, n) for t, _, n in jobs], ex.map(lambda j: run(j[1], CASES[j[2]][1], f'{j[0]}{j[2]}'), jobs)))
    for tool, cmd in ts.items():
        got[tool] = []
        for n, (label, calls, over) in enumerate(CASES):
            r = recs[(tool, n)]
            want = sum(price(u) for u in calls)
            peak = max(i + cw + cr for i, cw, cr, o in calls)
            flag = [f for f in r['flags'] if f['code'] == 'context_over_100k']
            check(f'[{tool}] {label}: cost is priced per call ({want:.5f})', abs(r['est_cost_usd'] - want) < 0.00002, f"{r['est_cost_usd']} vs {want}")
            check(f'[{tool}] {label}: peak_context is the biggest prompt ({peak})', r.get('peak_context') == peak, str(r.get('peak_context')))
            if over:
                check(f'[{tool}] {label}: flagged context_over_100k (warn) for {over} call(s)', len(flag) == 1 and flag[0]['sev'] == 'warn' and flag[0]['detail'].startswith(f'{over} of {len(calls)} API calls had a prompt above 100000 tokens (peak {peak})') and r['flagged'], str(r['flags']))
            else:
                check(f'[{tool}] {label}: no context_over_100k flag', not flag, str(r['flags']))
            got[tool].append((r['est_cost_usd'], r.get('peak_context'), [(f['code'], f['sev'], f['detail']) for f in r['flags']]))
    if len(ts) == 2:
        check('sh and ps1 record the same cost, peak and flags', got['sh'] == got['ps1'], f"{got['sh']} vs {got['ps1']}")
    shutil.rmtree(TMP, ignore_errors=True)


main()
print(summary(results))
sys.exit(0 if all(results) else 1)
