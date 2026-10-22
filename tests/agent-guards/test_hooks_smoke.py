"""Run the real hooks.json commands through sh (as Claude Code does) and check the verdicts. Run: python test_hooks_smoke.py"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SH = shutil.which('sh')
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def hook_commands(plugin, event=None, script=None):
    data = json.loads((ROOT / 'plugins' / plugin / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    out = []
    for evt, groups in data['hooks'].items():
        if event and evt != event:
            continue
        for g in groups:
            for h in g['hooks']:
                if script is None or script in h['command']:
                    out.append(h['command'])
    return out


def run_hook(plugin, command, payload, env):
    root = str(ROOT / 'plugins' / plugin)
    cmd = command.replace('${CLAUDE_PLUGIN_ROOT}', root)
    return subprocess.run([SH, '-c', cmd], input=json.dumps(payload) if payload is not None else '', capture_output=True, text=True, timeout=120, env=env)


def main():
    if not SH:
        check('sh available', False, 'no sh on PATH')
    else:
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ, AGENT_KIT_DATA=str(pathlib.Path(td) / 'kit'))
            for plugin in ('haiku-delegation', 'agent-guards', 'agent-eval', 'verification-runner'):
                for c in hook_commands(plugin, 'SessionStart'):
                    p = run_hook(plugin, c, {'hook_event_name': 'SessionStart', 'source': 'startup'}, env)
                    check(f'{plugin}: SessionStart hook runs and injects policy text', p.returncode == 0 and len(p.stdout.strip()) > 50, f'rc={p.returncode} {p.stderr[:200]}')
            env_guard = hook_commands('agent-guards', 'PreToolUse', 'guard-env-files')[0]
            p = run_hook('agent-guards', env_guard, {'agent_type': 'secret-candidate-lister', 'tool_name': 'Read', 'tool_input': {'file_path': '/srv/app/.env'}}, env)
            check('env guard blocks a real .env read (exit 2)', p.returncode == 2 and 'BLOCKED' in p.stderr, f'rc={p.returncode} {p.stderr[:200]}')
            p = run_hook('agent-guards', env_guard, {'agent_type': 'secret-candidate-lister', 'tool_name': 'Read', 'tool_input': {'file_path': '/srv/app/.env.example'}}, env)
            check('env guard allows .env.example (exit 0)', p.returncode == 0, f'rc={p.returncode} {p.stderr[:200]}')
            git_guard = hook_commands('agent-guards', 'PreToolUse', 'guard-git-readonly')[0]
            p = run_hook('agent-guards', git_guard, {'agent_type': 'changelog-summarizer', 'tool_name': 'Bash', 'tool_input': {'command': 'git push origin main'}}, env)
            check('git guard blocks a write command (exit 2)', p.returncode == 2, f'rc={p.returncode} {p.stderr[:200]}')
            p = run_hook('agent-guards', git_guard, {'agent_type': 'changelog-summarizer', 'tool_name': 'Bash', 'tool_input': {'command': 'git log --oneline -5'}}, env)
            check('git guard allows a read-only command (exit 0)', p.returncode == 0, f'rc={p.returncode} {p.stderr[:200]}')
            # input that cannot be read names no caller, and only changelog-summarizer is in scope: allowed
            git_cmd = git_guard.replace('${CLAUDE_PLUGIN_ROOT}', str(ROOT / 'plugins' / 'agent-guards'))
            p = subprocess.run([SH, '-c', git_cmd], input='not json', capture_output=True, text=True, timeout=120, env=env)
            check('git guard allows unparseable input (exit 0)', p.returncode == 0, f'rc={p.returncode} {p.stderr[:200]}')
            # the harness may write the input and leave stdin open: the hook must still decide, well inside its 30 s timeout
            # (before the fix it waited for the end of input until the harness killed it, and onFailure blocked the call)
            payload = json.dumps({'agent_type': 'changelog-summarizer', 'tool_name': 'Bash', 'tool_input': {'command': 'git push origin main'}})
            proc = subprocess.Popen([SH, '-c', git_cmd], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            proc.stdin.write(payload)
            proc.stdin.flush()
            start = time.monotonic()
            try:
                proc.wait(timeout=25)
                elapsed = time.monotonic() - start
                err = proc.stderr.read()
                check('git guard decides with stdin left open (exit 2, under 25 s)', proc.returncode == 2 and 'BLOCKED' in err, f'rc={proc.returncode} {elapsed:.1f}s {err[:200]}')
            except subprocess.TimeoutExpired:
                proc.kill()
                check('git guard decides with stdin left open (exit 2, under 25 s)', False, 'still running after 25 s')
            finally:
                proc.stdin.close()
            log = pathlib.Path(td, 'kit', 'hook-errors.log')
            check('an open hook stdin is traced in hook-errors.log', log.is_file() and 'hook input not closed' in log.read_text(encoding='utf-8'), str(log))
            # a hook with unparseable input must not crash the launcher chain for other agents
            p = run_hook('agent-guards', hook_commands('agent-guards', 'PreToolUse', 'guard-monitor-patterns')[0], {'agent_type': 'x', 'tool_name': 'Bash', 'tool_input': {'command': 'echo hi'}}, env)
            check('monitor guard lets a normal command through', p.returncode == 0, f'rc={p.returncode} {p.stderr[:200]}')
    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
