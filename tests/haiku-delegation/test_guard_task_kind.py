"""guard-task-kind (PreToolUse on the Agent tool): a brief for code-explorer or contracts-reader must start with `Task kind: <kind>`. Runs the PowerShell and the POSIX sh version
(whichever exist here) on the same hook inputs and requires the same exit code and a message that names the valid kinds. Run: python test_guard_task_kind.py"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'haiku-delegation' / 'scripts'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    out = {}
    if shutil.which('sh'):
        out['sh'] = ['sh', str(SCRIPTS / 'guard-task-kind.sh')]
    ps = (shutil.which('powershell.exe') or shutil.which('powershell')) if sys.platform == 'win32' else shutil.which('pwsh')   # not the Windows powershell.exe that WSL exposes through interop: it cannot open Linux paths
    if ps:
        out['ps1'] = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / 'guard-task-kind.ps1')]
    return out


def hook(subagent, prompt, tool='Agent'):
    return json.dumps({'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': {'description': 'x', 'prompt': prompt, 'subagent_type': subagent}})


CASES = [  # label, stdin, env, expected exit
    ('other agent is not checked', hook('log-triage', 'no kind line at all'), {}, 0),
    ('plugin-prefixed other agent is not checked', hook('haiku-delegation:doc-researcher', 'no kind line'), {}, 0),
    ('code-explorer locate', hook('code-explorer', 'Task kind: locate\nWhere is X'), {}, 0),
    ('code-explorer read', hook('code-explorer', 'Task kind: read\nAnswer'), {}, 0),
    ('code-explorer tests', hook('code-explorer', 'Task kind: tests\nList'), {}, 0),
    ('plugin-prefixed code-explorer', hook('haiku-delegation:code-explorer', 'Task kind: map\nImports'), {}, 0),
    ('several kinds, commas', hook('code-explorer', 'Task kind: locate, inventory\nBoth'), {}, 0),
    ('leading blank line is fine', hook('code-explorer', '\n\nTask kind: read\nAnswer'), {}, 0),
    ('contracts-reader schema', hook('contracts-reader', 'Task kind: schema\nRead db'), {}, 0),
    ('contracts-reader api-spec', hook('contracts-reader', 'Task kind: api-spec\nRead spec'), {}, 0),
    ('contracts-reader migrations, api-match', hook('contracts-reader', 'Task kind: migrations, api-match\nBoth'), {}, 0),
    ('triage log-triage', hook('triage', 'Task kind: log-triage\nRead the log'), {}, 0),
    ('infra-reader several kinds', hook('infra-reader', 'Task kind: pipeline-reader, dependency-reader\nBoth'), {}, 0),
    ('docs-reader doc-drafter', hook('haiku-delegation:docs-reader', 'Task kind: doc-drafter\nDraft'), {}, 0),
    ('compliance-lister citation-verifier', hook('compliance-lister', 'Task kind: citation-verifier\nClaims'), {}, 0),
    ('triage missing kind is blocked', hook('triage', 'Read the log'), {}, 2),
    ('a kind of another topic agent is blocked', hook('triage', 'Task kind: schema\nx'), {}, 2),
    ('compliance-lister with an old kind-less brief is blocked', hook('compliance-lister', 'List secrets in src/'), {}, 2),
    ('Task tool name alias', hook('code-explorer', 'Task kind: read\nA', tool='Task'), {}, 0),
    ('missing kind line is blocked', hook('code-explorer', 'Where is X defined?'), {}, 2),
    ('kind line not first is blocked', hook('code-explorer', 'Where is X defined?\nTask kind: locate'), {}, 2),
    ('contracts-reader missing kind is blocked', hook('contracts-reader', 'Read db/0001.sql'), {}, 2),
    ('a kind of the other agent is blocked', hook('code-explorer', 'Task kind: schema\nRead'), {}, 2),
    ('unknown kind is blocked', hook('contracts-reader', 'Task kind: banana\nRead'), {}, 2),
    ('one bad kind among good ones is blocked', hook('code-explorer', 'Task kind: locate, banana\nRead'), {}, 2),
    ('empty kind is blocked', hook('code-explorer', 'Task kind:\nRead'), {}, 2),
    ('empty prompt is blocked', hook('code-explorer', ''), {}, 2),
    ('TASK_KIND_GUARD=off allows', hook('code-explorer', 'no kind line'), {'TASK_KIND_GUARD': 'off'}, 0),
    ('TASK_KIND_GUARD=OFF (other case) does not disable', hook('code-explorer', 'no kind line'), {'TASK_KIND_GUARD': 'OFF'}, 2),
    ('uppercase TASK KIND is blocked (case-sensitive)', hook('code-explorer', 'TASK KIND: locate\nq'), {}, 2),
    ('lowercase task kind is blocked (case-sensitive)', hook('code-explorer', 'task kind: locate\nq'), {}, 2),
    ('subagent type in other case is not guarded', hook('Code-Explorer', 'no kind line'), {}, 0),
    ('CRLF line endings are fine', hook('code-explorer', 'Task kind: locate\r\nq'), {}, 0),
    ('unparseable input fails open', 'not json at all', {}, 0),
    ('empty input fails open', '', {}, 0),
]


def main():
    ts = tools()
    check('at least one guard version can run here', bool(ts))
    seen = {}
    for tool, cmd in ts.items():
        seen[tool] = []
        for label, stdin, env, want in CASES:
            p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=60, env=dict(os.environ, **env))
            seen[tool].append(p.returncode)
            check(f'[{tool}] {label}', p.returncode == want, f'exit {p.returncode}, want {want}: {p.stderr[:160]}')
        p = subprocess.run(cmd, input=hook('contracts-reader', 'no kind'), capture_output=True, text=True, timeout=60)
        check(f'[{tool}] the block message names the valid kinds and an example', all(k in p.stderr for k in ('schema', 'api-spec', 'migrations', 'api-match', 'Task kind:')), p.stderr)
    if len(ts) == 2:
        check('sh and ps1 return the same exit codes', seen['sh'] == seen['ps1'], f"{seen['sh']} vs {seen['ps1']}")
    # the kind words come from the brief (untrusted text): a glob character must not list the working folder, and a bad word is echoed only in a short plain form
    import tempfile
    with tempfile.TemporaryDirectory(prefix='kindguard_') as td:
        (pathlib.Path(td) / 'zzz_sentinel_file.txt').write_text('x', encoding='utf-8')
        for tool, cmd in ts.items():
            for label, kind_line in (('star', 'Task kind: *'), ('question mark', 'Task kind: ?'), ('bracket', 'Task kind: [a-z]*')):
                p = subprocess.run(cmd, input=hook('code-explorer', kind_line + '\nq'), capture_output=True, text=True, timeout=60, cwd=td)
                check(f'[{tool}] {label} in the kind line: blocked and the working folder is not listed', p.returncode == 2 and 'zzz_sentinel_file' not in p.stderr, p.stderr[:200])
            p = subprocess.run(cmd, input=hook('code-explorer', 'Task kind: <b>' + 'a' * 100 + '</b>\nq'), capture_output=True, text=True, timeout=60, cwd=td)
            check(f'[{tool}] a bad kind word is echoed short and without markup', p.returncode == 2 and '<b>' not in p.stderr and 'a' * 21 not in p.stderr, p.stderr[:200])
    hooks = json.loads((ROOT / 'plugins' / 'haiku-delegation' / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    pre = hooks['hooks'].get('PreToolUse', [])
    check('hooks.json registers guard-task-kind on the Agent tool through run.sh',
          any('Agent' in e.get('matcher', '') and any('guard-task-kind' in h['command'] and 'scripts/run.sh' in h['command'] for h in e['hooks']) for e in pre), str(pre))


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
