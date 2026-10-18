"""Issue #3: a subagent the user stopped never reaches SubagentStop, so it had no usage record and the annotator could not annotate it. The SubagentStart hook
(subagent-start-log, PowerShell and sh) now writes a start record, and annotate.py accepts a start-only run. Run: python test_stopped_run.py   (temp data folder)"""
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

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'agent-eval' / 'scripts'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='stoppedrun_'))
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    return capability_variants(SCRIPTS / 'subagent-start-log')


def start(cmd, payload, log, raw=None):
    env = dict(os.environ, AGENT_START_LOG=str(log), AGENT_KIT_DATA=str(TMP / 'kit'))
    return subprocess.run(cmd, input=raw if raw is not None else json.dumps(payload), capture_output=True, text=True, timeout=120, env=env)


def lines(log):
    return [json.loads(x) for x in pathlib.Path(log).read_text(encoding='utf-8').splitlines()] if pathlib.Path(log).exists() else []


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
    ts = tools()
    check('at least one start hook can run here', bool(ts))
    base = {'session_id': 'sess-1', 'transcript_path': str(TMP / 'projects' / 'proj' / 'sess-1.jsonl'), 'cwd': str(TMP), 'prompt_id': 'p1',
            'agent_id': 'a1b2c3d4e5f60718', 'agent_type': 'general-purpose', 'hook_event_name': 'SubagentStart'}
    for t, cmd in ts.items():
        log = TMP / f'starts-{t}.jsonl'
        p = start(cmd, base, log)
        check(f'[{t}] the hook exits 0 and prints nothing', p.returncode == 0 and not p.stdout.strip(), f'{p.returncode} {p.stdout[:100]} {p.stderr[:100]}')
        rec = lines(log)
        check(f'[{t}] one start record is written', len(rec) == 1, str(rec))
        if rec:
            r = rec[0]
            check(f'[{t}] the record has the ids, the agent type and the type "start"', r.get('type') == 'start' and r.get('agent_id') == base['agent_id'] and r.get('agent_type') == 'general-purpose' and r.get('session_id') == 'sess-1', str(r))
            tx = r.get('transcript', '').replace('\\', '/')
            check(f'[{t}] the transcript path points into the session\'s subagents folder', tx.endswith('/sess-1/subagents/agent-a1b2c3d4e5f60718.jsonl'), tx)
            check(f'[{t}] the record holds no prompt or message text', set(r) == {'schema', 'type', 'ts', 'session_id', 'agent_id', 'agent_type', 'cwd', 'transcript'}, str(sorted(r)))
        # input the hook must refuse to write (fail open, exit 0, nothing written)
        for label, payload, raw in (('an agent id that is a path', dict(base, agent_id='../../evil'), None), ('an agent id with a space', dict(base, agent_id='a b'), None),
                                    ('no agent id', {k: v for k, v in base.items() if k != 'agent_id'}, None), ('input that is not JSON', None, 'not json at all'), ('empty input', None, '')):
            bad = TMP / f'bad-{t}-{abs(hash(label))}.jsonl'
            p = start(cmd, payload, bad, raw=raw)
            check(f'[{t}] {label}: exit 0 and nothing written', p.returncode == 0 and not bad.exists(), f'{p.returncode} {p.stderr[:100]}')
        log2 = TMP / f'starts2-{t}.jsonl'
        start(cmd, dict(base, agent_id='aaaa1111', session_id='bad session!'), log2)
        r2 = lines(log2)
        check(f'[{t}] a session id with odd characters is left out of the transcript path', len(r2) == 1 and r2[0].get('transcript') == '' and r2[0].get('session_id') == '', str(r2))

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
