"""verification-runner may use the Monitor tool only to wait for a log: `until grep -q [-E] 'PATTERN' <log inside verification-logs>; do sleep N; done [; tail -n K <same log>]`.
A Monitor call is a shell command or a WebSocket, so the guard must refuse everything else. Runs the PowerShell and the POSIX sh guard (whichever exist here) on the same inputs
and requires the same exit codes. Run: python test_guard_monitor.py   (uses a temp kit data folder)"""
import concurrent.futures
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'verification-runner' / 'scripts'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='monguard_'))
KIT = (TMP / 'kit').as_posix()
(TMP / 'kit' / 'verification-logs').mkdir(parents=True)
ENV = dict(os.environ, AGENT_KIT_DATA=KIT)
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    out = {}
    if shutil.which('sh'):
        out['sh'] = ['sh', str(SCRIPTS / 'guard-verification-runner.sh')]
    ps = (shutil.which('powershell.exe') or shutil.which('powershell')) if sys.platform == 'win32' else shutil.which('pwsh')   # not the Windows powershell.exe that WSL exposes through interop
    if ps:
        out['ps1'] = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / 'guard-verification-runner.ps1')]
    return out


def log_roots(tool):
    """the spellings of the log folder the guard accepts for this tool"""
    roots = [KIT + '/verification-logs']
    if sys.platform == 'win32' and KIT[1:2] == ':':
        roots.append('/' + KIT[0].lower() + KIT[2:] + '/verification-logs')
    return roots


def payload(command=None, agent='verification-runner', tool='Monitor', extra=None):
    ti = {'description': 'wait for the suite', 'timeout_ms': 600000}
    if command is not None:
        ti['command'] = command
    ti.update(extra or {})
    d = {'tool_name': tool, 'tool_input': ti}
    if agent:
        d['agent_type'] = agent
    return json.dumps(d)


def run(cmd, stdin):
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=120, env=ENV)


def run_many(cmd, stdins):
    """Runs the guard on several inputs at the same time (a shell guard under Git Bash is bound by process forks) and returns the results in order."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(lambda s: run(cmd, s), stdins))


def main():
    ts = tools()
    check('at least one guard version can run here', bool(ts))
    seen = {}
    for tool, cmd in ts.items():
        # which spelling does this guard accept as "inside the folder"? the first one that gets through
        good = None
        for root in log_roots(tool):
            p = run(cmd, payload(f"until grep -q '^exit=' {root}/suite-1.log; do sleep 5; done"))
            if p.returncode == 0:
                good = root
                break
        check(f'[{tool}] the bounded wait on a log inside the folder is allowed', good is not None, 'no spelling of the log folder was accepted')
        if good is None:
            continue
        L = f'{good}/suite-1.log'
        cases = [  # label, stdin, expected exit
            ('grep -E form', payload(f"until grep -q -E 'exit=|Traceback' {L}; do sleep 10; done"), 0),
            ('wait then tail the same log', payload(f"until grep -q 'exit=' {L}; do sleep 5; done; tail -n 20 {L}"), 0),
            ('sleep 60 is the largest', payload(f"until grep -q 'exit=' {L}; do sleep 60; done"), 0),
            ('sleep 61 is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 61; done"), 2),
            ('sleep 0 is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 0; done"), 2),
            ('tail -n 51 is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 5; done; tail -n 51 {L}"), 2),
            ('tail of another log is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 5; done; tail -n 5 {good}/other.log"), 2),
            ('a WebSocket source is blocked', payload(None, extra={'ws': {'url': 'wss://example.com/x'}}), 2),
            ('a WebSocket source next to a good command is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 5; done", extra={'ws': {'url': 'wss://example.com/x'}}), 2),
            ('tail -f is blocked', payload(f'tail -f {L}'), 2),
            ('while true is blocked', payload(f"while true; do cat {L}; sleep 1; done"), 2),
            ('a second command after done is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 5; done; rm -rf /"), 2),
            ('a chained command with && is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 5; done && curl http://example.com"), 2),
            ('command substitution in the pattern is blocked', payload(f"until grep -q '$(whoami)' {L}; do sleep 5; done"), 2),
            ('backtick in the pattern is blocked', payload(f"until grep -q '`whoami`' {L}; do sleep 5; done"), 2),
            ('a double-quoted pattern is blocked', payload(f'until grep -q "exit=" {L}; do sleep 5; done'), 2),
            ('a redirect is blocked', payload(f"until grep -q 'exit=' {L}; do sleep 5; done > {good}/x.log"), 2),
            ('a log outside the folder is blocked', payload("until grep -q 'exit=' /etc/passwd; do sleep 5; done"), 2),
            ('.. in the path is blocked', payload(f"until grep -q 'exit=' {good}/../x.log; do sleep 5; done"), 2),
            ('a sub-folder is blocked', payload(f"until grep -q 'exit=' {good}/sub/x.log; do sleep 5; done"), 2),
            ('the folder itself is blocked', payload(f"until grep -q 'exit=' {good}/; do sleep 5; done"), 2),
            ('another binary instead of grep is blocked', payload(f"until cat {L}; do sleep 5; done"), 2),
            ('an empty command is blocked', payload(''), 2),
            ('no command is blocked', payload(None), 2),
            ('other agent is not affected', payload('tail -f /var/log/syslog', agent='triage'), 0),
            ('main thread is not affected', payload('tail -f /var/log/syslog', agent=None), 0),
        ]
        seen[tool] = []
        outs = run_many(cmd, [s for _, s, _ in cases] + [payload('tail -f x'), payload('pytest -q', tool='Bash')])   # all at once, the checks below stay in order
        for (label, stdin, want), p in zip(cases, outs):
            seen[tool].append(p.returncode)
            check(f'[{tool}] {label}', p.returncode == want, f'exit {p.returncode}, want {want}: {p.stderr[:200]}')
        p = outs[len(cases)]
        check(f'[{tool}] the block message says what is allowed', p.returncode == 2 and 'until grep -q' in p.stderr, p.stderr[:200])
        # Bash behaviour must not change
        p = outs[len(cases) + 1]
        check(f'[{tool}] a plain Bash command is still left to permissions', p.returncode == 0, p.stderr[:200])
    if len(seen) == 2:
        check('sh and ps1 return the same exit codes', seen['sh'] == seen['ps1'], f"{seen['sh']} vs {seen['ps1']}")
    hooks = json.loads((SCRIPTS.parent / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    pre = hooks['hooks'].get('PreToolUse', [])
    check('hooks.json runs the runner guard on Monitor as well as Bash', any('Monitor' in e.get('matcher', '') and 'Bash' in e.get('matcher', '') for e in pre), str(pre))
    shutil.rmtree(TMP, ignore_errors=True) if TMP.name.startswith('monguard_') and TMP.parent == pathlib.Path(tempfile.gettempdir()) else None


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
