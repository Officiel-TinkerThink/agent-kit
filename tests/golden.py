"""Golden records for guard capabilities that take hook input on stdin.

A record is a JSON list of cases: {id, stdin, env, exit, stdout, stderr}. It is made once from the PowerShell version
(Windows), and it must equal the POSIX sh version byte for byte (record() refuses to write it otherwise).
replay() then checks each implementation that runs on this machine against the same record: Windows runs both,
Linux runs sh only. The .ps1 variant is reported as not applicable where PowerShell does not exist."""
import concurrent.futures
import json
import os
import pathlib
import subprocess

from capability import capability_variants


def run_case(cmd, case):
    p = subprocess.run(cmd, input=case['stdin'], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, **case.get('env', {})))
    return {'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}


def run_all(jobs):
    """(cmd, case) pairs run side by side (a shell guard under Git Bash is bound by process forks)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(lambda job: run_case(*job), jobs))


def record(cases, script, path):
    """Run every case through sh and ps1 (both must exist), refuse to write unless they agree on every case, then write the
    PowerShell result as the record. Returns the list of disagreeing case ids (empty when the record was written)."""
    ts = capability_variants(script)
    if set(ts) != {'sh', 'ps1'}:
        raise SystemExit(f'record needs both implementations here, have {sorted(ts)}')
    jobs = [(ts[k], c) for c in cases for k in ('sh', 'ps1')]
    done = iter(run_all(jobs))
    golden, bad = [], []
    for c in cases:
        out = {k: next(done) for k in ('sh', 'ps1')}
        if out['sh'] != out['ps1']:
            bad.append(c['id'])
        golden.append({'id': c['id'], 'stdin': c['stdin'], 'env': c.get('env', {}), 'exit': out['ps1']['exit'],
                       'stdout': out['ps1']['stdout'], 'stderr': out['ps1']['stderr']})
    if not bad:
        pathlib.Path(path).parent.mkdir(exist_ok=True)
        pathlib.Path(path).write_text(json.dumps(golden, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return bad


def replay(path, script, name, results, check):
    """Check every case of the record through each implementation here. check(name, ok, extra) is the suite's own printer."""
    ts = capability_variants(script)
    check('at least one guard version can run here', bool(ts), '')
    cases = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    jobs = [(cmd, c) for k, cmd in ts.items() for c in cases]
    done = iter(run_all(jobs))
    for k in ts:
        for c in cases:
            got = next(done)
            want = {'exit': c['exit'], 'stdout': c['stdout'], 'stderr': c['stderr']}
            diff = [f for f in want if got[f] != want[f]]
            check(f'[{k}] {c["id"]} matches the record', not diff, f'differs in {diff}: exit {got["exit"]} want {want["exit"]}')
