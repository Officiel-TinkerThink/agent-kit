"""guard-turn-budget: a kit subagent is told once, at its N-th tool call, to stop and write its report with PARTIAL; it is never blocked again (the real cap
maxTurns = 3 x N is the safety margin). Main agent, unknown agents, the SubagentHandback call, bad input and old count files are covered by the recorded
cases (cases/guard-turn-budget.json, replayed through each implementation that runs here, see tests/golden.py). turn-budget.txt, the agent files
(maxTurns = 3 x N and the budget bullet) and hooks.json agree. A CRLF turn-budget.txt is checked here, because it needs the scripts in another folder.
Run: python test_guard_turn_budget.py"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import capability_variants, summary  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'agent-guards' / 'scripts'
CASES = Path(__file__).resolve().parent / 'cases'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools(stem):
    return capability_variants(SCRIPTS / stem)


def table():
    rows = {}
    for line in (SCRIPTS / 'turn-budget.txt').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            a, n = line.split()
            rows[a] = int(n)
    return rows


def call(agent_id='a1', agent_type='haiku-delegation:code-explorer', tool='Read'):
    p = {'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': {'file_path': 'x.txt'}}
    if agent_id is not None:
        p['agent_id'] = agent_id
    if agent_type is not None:
        p['agent_type'] = agent_type
    return p


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

    # behaviour: the recorded call sequences
    golden.replay(CASES / 'guard-turn-budget.json', SCRIPTS / 'guard-turn-budget', results, check)

    # a turn-budget.txt checked out with CRLF line ends (Windows, core.autocrlf) must still be read, not ignored (fail-open)
    n = rows['verification-runner']
    rt = 'verification-runner:verification-runner'
    for ver, cmd in tools('guard-turn-budget').items():
        sc = pathlib.Path(tempfile.mkdtemp(prefix='gtbcrlf_'))
        bud = pathlib.Path(tempfile.mkdtemp(prefix='gtb_'))
        for fn in ('lib.sh', 'guard-turn-budget.sh', 'guard-turn-budget.ps1'):
            shutil.copy(SCRIPTS / fn, sc / fn)
        (sc / 'turn-budget.txt').write_bytes((SCRIPTS / 'turn-budget.txt').read_text(encoding='utf-8').replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
        ccmd = ['sh', str(sc / 'guard-turn-budget.sh')] if ver == 'sh' else cmd[:-1] + [str(sc / 'guard-turn-budget.ps1')]
        (bud / 'turn-budget').mkdir()
        (bud / 'turn-budget' / 'c1').write_text(f'{n - 1}\n')
        r = subprocess.run(ccmd, input=json.dumps(call('c1', rt)), capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, AGENT_KIT_DATA=str(bud)))
        check(f'[{ver}] a CRLF turn-budget.txt is read: the N-th call is still blocked', r.returncode == 2 and 'PARTIAL' in r.stderr, f'{r.returncode} {r.stderr}')
        shutil.rmtree(sc, ignore_errors=True)
        shutil.rmtree(bud, ignore_errors=True)

    print(summary(results))
    sys.exit(0 if all(results) else 1)


main()
