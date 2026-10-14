"""Issue #4: the guard blocks reach the model behind Claude Code's own "hook error" label, which the kit cannot change. The text after it must say that the block is
intentional and what to do instead, and the bulk-read message must say that chunked reads are fine for any purpose, which the hook really allows.
Runs the PowerShell and the POSIX sh version (whichever exist here). Run: python test_guard_messages.py"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-guards' / 'scripts'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='gmsg_'))
BIG = TMP / 'big.py'
BIG.write_text('\n'.join(f'line {i}' for i in range(300)) + '\n', encoding='utf-8')
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def posix_path(p):
    """C:/Users/x -> /c/Users/x on Windows (Git Bash form); unchanged elsewhere"""
    q = p.as_posix()
    return '/' + q[0].lower() + q[2:] if sys.platform == 'win32' and q[1:2] == ':' else q


def tools(stem):
    out = {}
    if shutil.which('sh'):
        out['sh'] = ['sh', str(SCRIPTS / f'{stem}.sh')]
    ps = (shutil.which('powershell.exe') or shutil.which('powershell')) if sys.platform == 'win32' else shutil.which('pwsh')   # not the Windows powershell.exe that WSL exposes through interop
    if ps:
        out['ps1'] = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / f'{stem}.ps1')]
    return out


def run(cmd, payload, env=None):
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, timeout=120, env=dict(os.environ, **(env or {})), cwd=str(TMP))


def main():
    bulk = tools('check-bulk-read')
    envg = tools('guard-env-files')
    check('at least one version of each guard can run here', bool(bulk) and bool(envg))
    read_whole = {'tool_name': 'Read', 'tool_input': {'file_path': BIG.as_posix()}, 'cwd': TMP.as_posix(), 'hook_event_name': 'PreToolUse'}
    for t, cmd in bulk.items():
        big = posix_path(BIG) if t == 'sh' else BIG.as_posix()   # the sh guard treats only /-rooted paths as absolute (Git Bash form on Windows)
        rw = dict(read_whole, tool_input={'file_path': big})
        p = run(cmd, rw, {'BULK_READ_MIN_LINES': '50'})
        err = p.stderr
        check(f'[{t}] a whole-file read of a long file is blocked (exit 2)', p.returncode == 2, f'exit {p.returncode} {err[:160]}')
        check(f'[{t}] the message says the block is intentional', 'intentional guard' in err, err[:200])
        check(f'[{t}] the message says chunked reads are allowed for any purpose, reviews included', 'in chunks is always allowed' in err and 'review' in err and 'offset/limit' in err, err[:300])
        check(f'[{t}] the message still names the agent to delegate to', "subagent_type='" in err, err[:300])
        for label, ti in (('offset', {'file_path': big, 'offset': 10}), ('limit', {'file_path': big, 'limit': 100}), ('offset and limit', {'file_path': big, 'offset': 1, 'limit': 150})):
            p = run(cmd, dict(rw, tool_input=ti), {'BULK_READ_MIN_LINES': '50'})
            check(f'[{t}] a read with {label} passes, as the message promises', p.returncode == 0, f'exit {p.returncode} {p.stderr[:160]}')
        p = run(cmd, dict(rw, agent_id='sub1', agent_type='code-explorer'), {'BULK_READ_MIN_LINES': '50'})
        check(f'[{t}] a subagent reads freely', p.returncode == 0, p.stderr[:160])
    dir_grep = {'tool_name': 'Grep', 'tool_input': {'pattern': 'x', 'path': str(TMP)}, 'agent_id': 'sub1', 'agent_type': 'compliance-lister', 'hook_event_name': 'PreToolUse'}
    for t, cmd in envg.items():
        p = run(cmd, dict(dir_grep, agent_type='secret-candidate-lister'))
        check(f'[{t}] a directory-wide Grep by a guarded agent is blocked with the recovery text', p.returncode == 2 and 'intentional guard' in p.stderr and '.env' in p.stderr, f'exit {p.returncode} {p.stderr[:200]}')
        p = run(cmd, {'tool_name': 'Read', 'tool_input': {'file_path': str(TMP / '.env')}, 'agent_id': 'sub1', 'agent_type': 'secret-candidate-lister', 'hook_event_name': 'PreToolUse'})
        check(f'[{t}] a real .env read is blocked and says so', p.returncode == 2 and 'intentional guard' in p.stderr, f'exit {p.returncode} {p.stderr[:200]}')
        p = run(cmd, {'tool_name': 'Read', 'tool_input': {'file_path': str(TMP / '.env.example')}, 'agent_id': 'sub1', 'agent_type': 'secret-candidate-lister', 'hook_event_name': 'PreToolUse'})
        check(f'[{t}] an example env file stays readable', p.returncode == 0, p.stderr[:160])
        p = run(cmd, dict(dir_grep, agent_type='triage'))
        check(f'[{t}] an unguarded agent is not affected', p.returncode == 0, p.stderr[:160])
    print(f'{sum(results)}/{len(results)} passed')
    shutil.rmtree(TMP, ignore_errors=True) if TMP.name.startswith('gmsg_') and TMP.parent == pathlib.Path(tempfile.gettempdir()) else None
    sys.exit(0 if all(results) else 1)


main()
