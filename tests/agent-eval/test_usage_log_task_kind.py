"""The merged agents (code-explorer, contracts-reader) serve several kinds of task. The usage-log hook reads the brief's `Task kind: <kind>` line and applies\nthe footer checks (Coverage, Reconciliation) of that kind only. Runs the PowerShell and the POSIX sh hook (whichever exist here) and requires identical flags.
Run: python test_usage_log_task_kind.py   (uses a temp log and data folder)"""
import json
from concurrent.futures import ThreadPoolExecutor
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-eval' / 'scripts'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='kindtest_'))
results = []
PLAIN = 'A plain answer with enough text to count as an answer, with nothing else in it.'
BOTH = PLAIN + '\nCoverage: read 1 file.\nReconciliation: expected 4 / listed 4.'
COV = PLAIN + '\nCoverage: read 1 file.'


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    out = {}
    if shutil.which('sh'):
        out['sh'] = ['sh', str(SCRIPTS / 'subagent-usage-log.sh')]
    ps = (shutil.which('powershell.exe') or shutil.which('powershell')) if sys.platform == 'win32' else shutil.which('pwsh')   # not the Windows powershell.exe that WSL exposes through interop: it cannot open Linux paths
    if ps:
        out['ps1'] = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / 'subagent-usage-log.ps1')]
    return out


def transcript(brief, answer, n):
    ts = '2026-10-14T10:00:0%d.000Z'
    use = {'input_tokens': 2, 'output_tokens': 100, 'cache_read_input_tokens': 1000, 'cache_creation_input_tokens': 500}
    rows = [{'type': 'user', 'timestamp': ts % 0, 'message': {'role': 'user', 'content': brief}},
            {'type': 'assistant', 'timestamp': ts % 1, 'uuid': 'a', 'message': {'id': 'm1', 'model': 'claude-haiku-5-5', 'usage': use, 'content': [{'type': 'thinking', 'thinking': ''}]}},
            {'type': 'assistant', 'timestamp': ts % 2, 'uuid': 'b', 'message': {'id': 'm2', 'model': 'claude-haiku-5-5', 'usage': use, 'content': [{'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': answer}}]}}]
    p = TMP / f't{n}.jsonl'
    p.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    return p


def flags(cmd, agent, brief, answer, n):
    tp = transcript(brief, answer, n)
    inp = TMP / f'in{n}.json'
    inp.write_text(json.dumps({'session_id': 's', 'agent_id': f'agent{n}', 'agent_type': agent, 'effort': {'level': 'low'}, 'cwd': str(TMP), 'agent_transcript_path': str(tp)}), encoding='utf-8')
    log = TMP / f'log{n}.jsonl'
    if log.exists():
        log.unlink()
    env = dict(os.environ, AGENT_USAGE_LOG=str(log), AGENT_KIT_DATA=str(TMP / 'kit'))
    subprocess.run(cmd + ['-SelfTestInput', str(inp)], env=env, check=True, capture_output=True, timeout=600)
    rec = json.loads(log.read_text(encoding='utf-8').splitlines()[-1])
    return sorted(f['detail'] for f in rec['flags'] if f['code'] == 'footer_missing')


CASES = [  # (label, agent, brief, answer, expected footer_missing details)
    ('contracts-reader schema: both footers required', 'contracts-reader', 'Task kind: schema\nRead db/0001.sql', PLAIN, ['no Coverage line', 'no Reconciliation line']),
    ('contracts-reader schema: footers present', 'contracts-reader', 'Task kind: schema\nRead db/0001.sql', BOTH, []),
    ('contracts-reader api-spec: Reconciliation required', 'contracts-reader', 'Task kind: api-spec\nRead api/openapi.yaml', COV, ['no Reconciliation line']),
    ('contracts-reader migrations: no footers required', 'contracts-reader', 'Task kind: migrations\nCheck migrations/', PLAIN, []),
    ('contracts-reader api-match: no footers required', 'contracts-reader', 'Task kind: api-match\nCompare routes', PLAIN, []),
    ('contracts-reader mixed kinds: schema applies', 'contracts-reader', 'Task kind: migrations, schema\nBoth', PLAIN, ['no Coverage line', 'no Reconciliation line']),
    ('contracts-reader with no kind line: nothing required', 'contracts-reader', 'Read db/0001.sql', PLAIN, []),
    ('code-explorer inventory: Coverage required', 'code-explorer', 'Task kind: inventory\nList env vars', PLAIN, ['no Coverage line']),
    ('code-explorer inventory: Coverage present', 'code-explorer', 'Task kind: inventory\nList env vars', COV, []),
    ('code-explorer locate: Coverage required', 'code-explorer', 'Task kind: locate\nWhere is X', PLAIN, ['no Coverage line']),
    ('code-explorer map: Coverage required', 'code-explorer', 'Task kind: map\nImports of pkg', PLAIN, ['no Coverage line']),
    ('code-explorer read: no footers required', 'code-explorer', 'Task kind: read\nWhat does the file say', PLAIN, []),
    ('code-explorer tests: no footers required', 'code-explorer', 'Task kind: tests\nList tests', PLAIN, []),
    ('code-explorer with no kind line: nothing required', 'code-explorer', 'Where is X', PLAIN, []),
    ('whole words only: roadmap is not map', 'code-explorer', 'Task kind: roadmap\nq', PLAIN, []),
    ('whole words only: relocate is not locate', 'code-explorer', 'Task kind: relocate\nq', PLAIN, []),
    ('kind text running on into the sentence still finds the kind word', 'code-explorer', 'Task kind: locate and report back\nq', PLAIN, ['no Coverage line']),
    ('capitalised kind is not a kind (case-sensitive, like the guard)', 'code-explorer', 'Task kind: Locate\nq', PLAIN, []),
    ('infra-reader pipeline-reader: both footers required', 'infra-reader', 'Task kind: pipeline-reader\nRead ci.yml', PLAIN, ['no Coverage line', 'no Reconciliation line']),
    ('infra-reader dependency-reader: none required', 'infra-reader', 'Task kind: dependency-reader\nRead manifests', PLAIN, []),
    ('triage log-triage: none required', 'triage', 'Task kind: log-triage\nRead the log', PLAIN, []),
    ('compliance-lister mixed kinds: none required', 'compliance-lister', 'Task kind: audit-coverage-lister, citation-verifier\nBoth', PLAIN, []),
    ('plugin-prefixed agent type works', 'agent-eval:code-explorer', 'Task kind: inventory\nList env vars', PLAIN, ['no Coverage line']),
    ('legacy schema-reader still requires both', 'schema-reader', 'do the task', PLAIN, ['no Coverage line', 'no Reconciliation line']),
    ('legacy bulk-reader requires none', 'bulk-reader', 'do the task', PLAIN, []),
]


def main():
    ts = tools()
    check('at least one hook can run here', bool(ts))
    got = {}
    n = 0
    for tool, cmd in ts.items():
        # one run of the hook takes about 20 s on Windows (process start-up): run the cases side by side, each with its own files
        jobs = []
        for label, agent, brief, answer, want in CASES:
            n += 1
            jobs.append((n, label, agent, brief, answer, want))
        with ThreadPoolExecutor(max_workers=6) as pool:
            haves = list(pool.map(lambda j: flags(cmd, j[2], j[3], j[4], j[0]), jobs))
        got[tool] = haves
        for (_, label, _, _, _, want), have in zip(jobs, haves):
            check(f'[{tool}] {label}', have == sorted(want), f'{have} != {sorted(want)}')
    if len(ts) == 2:
        check('sh and ps1 record identical footer flags', got['sh'] == got['ps1'], f"{got['sh']} vs {got['ps1']}")


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
