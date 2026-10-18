"""Issue #3: a subagent the user stopped never reaches SubagentStop, so it had no usage record and the annotator could not annotate it. The SubagentStart hook
(subagent-start-log, PowerShell and sh) now writes a start record, and annotate.py accepts a start-only run. The hook's behaviour is replayed from
cases/subagent-start-log.json through each implementation that runs here (see tests/golden.py); annotate.py is checked here directly.
Run: python test_stopped_run.py   (temp data folder)"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import summary  # noqa: E402
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'agent-eval' / 'scripts'
CASES = Path(__file__).resolve().parent / 'cases'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='stoppedrun_'))
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def annotation(agent_id, tag):
    d = TMP / 'kit' / 'eval' / 'inbox'
    d.mkdir(parents=True, exist_ok=True)
    f = d / f'{agent_id}-{tag}.json'
    f.write_text(json.dumps({
        'run_agent_id': agent_id, 'outcome': 'partial', 'code': 'omission', 'severity': 'low',
        'summary': 'The stopped run listed 3 of 5 files before it was stopped.', 'expected': 'All five files listed, as the brief asked.',
        'claim': 'The run was stopped by the user before it finished its list.', 'verified': 'yes',
        'evidence': [{'ref': 'transcript:1', 'note': 'the transcript ends after the third file'}]}), encoding='utf-8')
    return f


def annotate(f, log=None):
    env = dict(os.environ, AGENT_KIT_DATA=str(TMP / 'kit'), AGENT_START_LOG=str(log or (TMP / 'none.jsonl')))
    return subprocess.run([sys.executable, str(SCRIPTS / 'annotate.py'), '--file', str(f)], capture_output=True, text=True, timeout=60, env=env)


def main():
    # the start hook: recorded behaviour, replayed through each implementation here
    golden.replay(CASES / 'subagent-start-log.json', SCRIPTS / 'subagent-start-log', results, check)

    # the annotator side: a start-only run can be annotated; a normal run and unknown ids behave as before
    log = TMP / 'starts-annot.jsonl'
    log.write_text(json.dumps({'schema': 'agent-start/1', 'type': 'start', 'ts': '2026-10-14T10:00:00.000Z', 'session_id': 's', 'agent_id': 'stopped0001', 'agent_type': 'general-purpose', 'cwd': 'x', 'transcript': 't'}) + '\n', encoding='utf-8')
    p = annotate(annotation('stopped0001', 'a'), log)
    check('annotate.py accepts a run that only has a start record', p.returncode == 0 and 'RECORDED' in p.stdout, p.stdout + p.stderr)
    ann = [json.loads(x) for x in (TMP / 'kit' / 'eval' / 'annotations.jsonl').read_text(encoding='utf-8').splitlines()] if (TMP / 'kit' / 'eval' / 'annotations.jsonl').exists() else []
    check('the annotation says the run record was start-only and keeps the agent type', ann and ann[-1].get('run_record') == 'start-only' and ann[-1].get('run_agent_id') == 'stopped0001' and ann[-1].get('agent_type') == 'general-purpose', str(ann[-1:]))
    p = annotate(annotation('neverseen99', 'b'), log)
    check('an agent id with neither a run nor a start record is still rejected', p.returncode == 2 and 'REJECTED' in p.stdout, p.stdout + p.stderr)
    usage = TMP / 'kit' / 'usage'
    usage.mkdir(parents=True, exist_ok=True)
    (usage / 'agent-usage.jsonl').write_text(json.dumps({'schema': 'agent-usage/2', 'type': 'run', 'agent_id': 'finished01', 'agent_type': 'code-explorer', 'effort': 'low'}) + '\n', encoding='utf-8')
    p = annotate(annotation('finished01', 'c'), log)
    check('a finished run is annotated as before', p.returncode == 0 and 'RECORDED' in p.stdout, p.stdout + p.stderr)
    ann = [json.loads(x) for x in (TMP / 'kit' / 'eval' / 'annotations.jsonl').read_text(encoding='utf-8').splitlines()]
    check('a finished run keeps its effort and is marked run', ann[-1].get('run_record') == 'run' and ann[-1].get('effort') == 'low' and ann[-1].get('agent_type') == 'code-explorer', str(ann[-1]))
    # a start record and a run record for the same id: the run record wins
    log.write_text(json.dumps({'schema': 'agent-start/1', 'type': 'start', 'agent_id': 'finished01', 'agent_type': 'general-purpose'}) + '\n', encoding='utf-8')
    p = annotate(annotation('finished01', 'd'), log)
    ann = [json.loads(x) for x in (TMP / 'kit' / 'eval' / 'annotations.jsonl').read_text(encoding='utf-8').splitlines()]
    check('when both records exist the run record wins', p.returncode == 0 and ann[-1].get('run_record') == 'run' and ann[-1].get('agent_type') == 'code-explorer', p.stdout + str(ann[-1]))

    hooks = json.loads((SCRIPTS.parent / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    cmds = [h['command'] for e in hooks['hooks'].get('SubagentStart', []) for h in e['hooks']]
    check('hooks.json runs subagent-start-log on SubagentStart through run.sh, next to inject-context', any('subagent-start-log' in c and 'scripts/run.sh' in c for c in cmds) and any('inject-context' in c for c in cmds), str(cmds))
    ann_md = (SCRIPTS.parent / 'agents' / 'annotator.md').read_text(encoding='utf-8')
    check('annotator.md tells the agent to look in agent-starts.jsonl when there is no run record', 'agent-starts.jsonl' in ann_md and 'never finished' in ann_md)
    print(summary(results))
    shutil.rmtree(TMP, ignore_errors=True) if TMP.name.startswith('stoppedrun_') and TMP.parent == pathlib.Path(tempfile.gettempdir()) else None
    sys.exit(0 if all(results) else 1)


main()
