"""guard-turn-budget: a kit subagent is told once, at its N-th tool call, to stop and write its report with PARTIAL; it is never blocked again (the real cap
maxTurns = 3 x N is the safety margin). Main agent, unknown agents, the SubagentHandback call and bad input are never touched. turn-budget.txt, the agent files
(maxTurns = 3 x N and the budget bullet) and hooks.json agree. Runs the PowerShell and the POSIX sh version (whichever exist here). Run: python test_guard_turn_budget.py"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capability import capability_variants, summary  # noqa: E402
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'agent-guards' / 'scripts'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools(stem):
    return capability_variants(SCRIPTS / stem)


def run(cmd, payload, data, raw=None):
    text = raw if raw is not None else json.dumps(payload)
    return subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=120, env=dict(os.environ, AGENT_KIT_DATA=str(data)))


def call(agent_id='a1', agent_type='haiku-delegation:code-explorer', tool='Read'):
    p = {'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': {'file_path': 'x.txt'}}
    if agent_id is not None:
        p['agent_id'] = agent_id
    if agent_type is not None:
        p['agent_type'] = agent_type
    return p


def table():
    rows = {}
    for line in (SCRIPTS / 'turn-budget.txt').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            a, n = line.split()
            rows[a] = int(n)
    return rows


def main():
    rows = table()
    # table, agent files and hooks.json agree
    files = {}
    for p in (ROOT / 'plugins').glob('*/agents/*.md'):
        s = p.read_text(encoding='utf-8').replace('\r\n', '\n')
        files[re.search(r'^name: (\S+)', s, re.M).group(1)] = s
    check('every agent file has a row in turn-budget.txt and every row has an agent file', set(files) == set(rows), f'{sorted(set(files) ^ set(rows))}')
    for name, n in sorted(rows.items()):
        s = files.get(name, '')
        m = re.search(r'^maxTurns: (\d+)$', s, re.M)
        check(f'{name}: maxTurns is 3 x {n}', bool(m) and int(m.group(1)) == 3 * n, m.group(0) if m else 'no maxTurns')
        check(f'{name}: the file tells the agent its budget ({n} tool calls) and PARTIAL', f'- Turn budget: you have about {n} tool calls.' in s and '`PARTIAL`' in s)
    hooks = json.loads((ROOT / 'plugins' / 'agent-guards' / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    pre = hooks['hooks']['PreToolUse']
    check('hooks.json runs guard-turn-budget on every tool (matcher .*)', any(e.get('matcher') == '.*' and any('guard-turn-budget' in h['command'] for h in e['hooks']) for e in pre), str(pre))

    outputs = {}
    for ver, cmd in tools('guard-turn-budget').items():
        tmp = pathlib.Path(tempfile.mkdtemp(prefix='gtb_'))
        bud = tmp / 'turn-budget'
        n = rows['verification-runner']
        rt = 'verification-runner:verification-runner'
        seq = []
        order = [1, 2, 3] + list(range(n - 2, n + 3))   # the first calls from a fresh count, then (count skipped ahead) the calls around the budget: fewer process starts
        for i in order:
            if i == n - 2:
                (bud / 'r1').write_text(f'{n - 3}\n')
            r = run(cmd, call('r1', rt), tmp)
            seq.append((i, r.returncode, r.stderr.strip()))
        quiet = [i for i, rc, _ in seq if rc == 0]
        blocked = [(i, err) for i, rc, err in seq if rc == 2]
        check(f'[{ver}] calls before the budget pass, call {n} is blocked once, later calls pass again', quiet == [i for i in order if i != n] and len(blocked) == 1 and blocked[0][0] == n, str(seq))
        msg = blocked[0][1] if blocked else ''
        check(f'[{ver}] the block says: intentional guard, budget {n}, stop, report, PARTIAL', 'intentional guard' in msg and f'({n} tool calls)' in msg and 'PARTIAL' in msg and 'final report' in msg, msg)
        outputs[ver] = msg
        check(f'[{ver}] the count is kept per agent id in turn-budget/<id>', (bud / 'r1').read_text().strip() == str(n + 2))

        # main agent and unknown agents are never counted
        for label, payload in (('main agent (no agent_id)', call(None, None)), ('unknown agent type', call('g1', 'general-purpose')), ('agent_id without type', call('g2', None))):
            r = run(cmd, payload, tmp)
            check(f'[{ver}] {label}: not counted, not blocked', r.returncode == 0 and not (bud / 'g1').exists() and not (bud / 'g2').exists(), r.stderr)
        # the report call is never counted or blocked
        (bud / 'h1').write_text(f'{n - 1}\n')
        r = run(cmd, call('h1', rt, tool='SubagentHandback'), tmp)
        check(f'[{ver}] SubagentHandback is neither counted nor blocked', r.returncode == 0 and (bud / 'h1').read_text().strip() == str(n - 1), r.stderr)
        r = run(cmd, call('h1', rt), tmp)
        check(f'[{ver}] ... and the next real tool call is the N-th', r.returncode == 2, r.stderr)
        # two agents are counted apart
        (bud / 'k1').write_text(f'{n - 1}\n')
        r1 = run(cmd, call('k2', rt), tmp)
        r2 = run(cmd, call('k1', rt), tmp)
        check(f'[{ver}] another agent is counted on its own', r1.returncode == 0 and r2.returncode == 2, f'{r1.stderr} {r2.stderr}')
        # plain agent_type without the plugin prefix works too
        (bud / 'p1').write_text(f'{n - 1}\n')
        r = run(cmd, call('p1', 'verification-runner'), tmp)
        check(f'[{ver}] agent_type without a plugin prefix is matched', r.returncode == 2, r.stderr)
        # a damaged count file starts again at 1
        (bud / 'd1').write_text('garbage\n')
        r = run(cmd, call('d1', rt), tmp)
        check(f'[{ver}] a damaged count file is treated as 0', r.returncode == 0 and (bud / 'd1').read_text().strip() == '1', r.stderr)
        # fail open: bad input, bad ids
        for label, kw in (('not JSON', {'raw': 'this is not json'}), ('empty input', {'raw': ''}), ('id with path characters', {'payload': call('../evil', rt)})):
            before = sorted(p.name for p in tmp.rglob('*'))
            r = run(cmd, kw.get('payload'), tmp, raw=kw.get('raw'))
            check(f'[{ver}] {label}: passes and writes nothing', r.returncode == 0 and sorted(p.name for p in tmp.rglob('*')) == before, r.stderr)
        # count files of finished runs older than a day are removed when a new agent starts
        old = bud / 'old1'
        old.write_text('7\n')
        t = time.time() - 3 * 86400
        os.utime(old, (t, t))
        keep = bud / 'fresh1'
        keep.write_text('3\n')
        r = run(cmd, call('n1', rt), tmp)
        check(f'[{ver}] a new agent clears count files older than a day, keeps recent ones', r.returncode == 0 and not old.exists() and keep.exists(), r.stderr)
        # a turn-budget.txt checked out with CRLF line ends (Windows, core.autocrlf) must still be read, not ignored (fail-open)
        sc = pathlib.Path(tempfile.mkdtemp(prefix='gtbcrlf_'))
        for fn in ('lib.sh', 'guard-turn-budget.sh', 'guard-turn-budget.ps1'):
            shutil.copy(SCRIPTS / fn, sc / fn)
        (sc / 'turn-budget.txt').write_bytes((SCRIPTS / 'turn-budget.txt').read_text(encoding='utf-8').replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
        ccmd = ['sh', str(sc / 'guard-turn-budget.sh')] if ver == 'sh' else cmd[:-1] + [str(sc / 'guard-turn-budget.ps1')]
        (bud / 'c1').write_text(f'{n - 1}\n')
        r = run(ccmd, call('c1', rt), tmp)
        check(f'[{ver}] a CRLF turn-budget.txt is read: the N-th call is still blocked', r.returncode == 2 and 'PARTIAL' in r.stderr, f'{r.returncode} {r.stderr}')
        shutil.rmtree(sc, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)

    if len(outputs) == 2:
        check('sh and ps1 print the same block message', outputs['sh'] == outputs['ps1'], str(outputs))
    print(summary(results))
    sys.exit(0 if all(results) else 1)


main()
