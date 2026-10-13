"""Tests for Layers 2-4: annotate.py validation, guard-annotator.ps1, and agent_eval.py (queue, judge with a stub, review, export, report).
Uses a throwaway base directory (AGENT_EVAL_BASE) so the real logs are never touched. Run: python test_eval_pipeline.py"""
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-eval' / 'scripts'
EVALDIR = SCRIPTS
GUARD = SCRIPTS / 'guard-annotator.ps1'
BASE = pathlib.Path(tempfile.mkdtemp(prefix='evaltest_')).resolve()
for d in ('usage', 'eval/inbox', 'agents'):
    (BASE / d).mkdir(parents=True)
(BASE / 'agents' / 'schema-reader.md').write_text('---\nname: schema-reader\n---\nYou read schemas.\n- Counts must reconcile.\n', encoding='utf-8')
os.environ['AGENT_KIT_DATA'] = str(BASE).replace('\\', '/')
os.environ['AGENT_KIT_AGENT_DIRS'] = str(BASE / 'agents')
sys.path.insert(0, str(SCRIPTS))
import agent_eval as ev  # noqa: E402

passed = failed = 0


def check(name, cond, extra=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print('FAIL', name, extra)


def make_run(aid, agent='schema-reader', flags=None, answer='Answer text that is long enough.', prompt='list tables', ts='2026-10-12T10:00:00+00:00', write_tx=True):
    tp = BASE / ('tx_%s.jsonl' % aid)
    rows = [{'type': 'user', 'message': {'role': 'user', 'content': prompt}},
            {'type': 'assistant', 'message': {'id': 'm', 'content': [{'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': answer}}]}}]
    tp.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    rec = {'schema': 'agent-usage/2', 'type': 'run', 'ts': ts, 'session_id': 's', 'agent_id': aid, 'agent_type': agent, 'effort': 'medium', 'models': ['claude-haiku-5-5'],
           'cwd': str(BASE), 'est_cost_usd': 0.001, 'flagged': bool(flags), 'flags': flags or [], 'transcript': str(tp),
           'transcript_sha256': hashlib.sha256(tp.read_bytes()).hexdigest().upper()}
    with open(BASE / 'usage' / 'agent-usage.jsonl', 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(rec) + '\n')
    return rec


make_run('aaa111', flags=[{'code': 'reconciliation_mismatch', 'sev': 'fail', 'detail': 'expected 4 / listed 3'}])
make_run('bbb222', ts='2026-10-12T09:00:00+00:00')
make_run('ccc333', flags=[{'code': 'guard_blocked', 'sev': 'info', 'detail': '1 blocked'}])
make_run('ddd444')


# ------------------------------------------------------------ annotate.py
def annotate(obj, name, raw=None):
    p = BASE / 'eval' / 'inbox' / name
    p.write_text(raw if raw is not None else json.dumps(obj), encoding='utf-8')
    r = subprocess.run([sys.executable, str(SCRIPTS / 'annotate.py'), '--file', str(p)], capture_output=True, text=True, env=dict(os.environ))
    return r.returncode, r.stdout


GOODANN = {'run_agent_id': 'bbb222', 'outcome': 'wrong', 'code': 'wrong_count', 'severity': 'medium', 'verified': 'yes',
           'claim': 'The caller says the table count was 3 but the file defines 4 tables.',
           'summary': 'The answer listed 3 tables; the SQL file defines 4 CREATE TABLE statements, so one table was dropped.',
           'expected': 'List all 4 tables and report expected 4 / listed 4.',
           'evidence': [{'ref': 'schema.sql:1', 'note': 'first CREATE TABLE'}, {'ref': 'transcript:final answer', 'note': 'lists three names'}],
           'suggested_fix': 'Count CREATE TABLE statements with Grep and compare with the sections written before answering.'}
rc, out = annotate(GOODANN, 'ok1.json')
check('valid annotation recorded', rc == 0 and 'RECORDED' in out, out)
lines = (BASE / 'eval' / 'annotations.jsonl').read_text(encoding='utf-8').splitlines()
a = json.loads(lines[0])
check('annotation enriched from the run', a['agent_type'] == 'schema-reader' and a['effort'] == 'medium' and a['annotated_by'] == 'annotator-agent' and a['source_sha256'])
bad = {
    'unknown run': dict(GOODANN, run_agent_id='zzz999'),
    'last not allowed': dict(GOODANN, run_agent_id='last'),
    'last:type not allowed': dict(GOODANN, run_agent_id='last:schema-reader'),
    'bad outcome': dict(GOODANN, outcome='terrible'),
    'bad code': dict(GOODANN, code='mystery'),
    'bad severity': dict(GOODANN, severity='critical'),
    'bad verified': dict(GOODANN, verified='maybe'),
    'summary too short': dict(GOODANN, summary='too short'),
    'summary too long': dict(GOODANN, summary='x' * 501),
    'evidence empty': dict(GOODANN, evidence=[]),
    'evidence malformed': dict(GOODANN, evidence=[{'ref': 'a'}]),
    'evidence too many': dict(GOODANN, evidence=[{'ref': 'a:1', 'note': 'n'}] * 7),
    'disputed but verified yes': dict(GOODANN, outcome='disputed', verified='yes'),
    'wrong but verified no': dict(GOODANN, outcome='wrong', verified='no'),
    'aws key in text': dict(GOODANN, summary='The answer printed AKIAABCDEFGHIJKLMNOP in the output near the top.'),
    'url credential': dict(GOODANN, summary='The answer printed postgres://svc:Hunter2Pass@db/x in the output.'),
    'sonar token': dict(GOODANN, expected='Never print squ_' + 'a1b2c3d4e5' * 4 + ' anywhere in the answer.'),
}
for name, obj in bad.items():
    rc, out = annotate(obj, 'bad_%s.json' % name.replace(' ', '_').replace(':', '_'))
    check('rejects: ' + name, rc == 2 and 'REJECTED' in out, out[:120])
missing = dict(GOODANN)
del missing['expected']
rc, out = annotate(missing, 'bad_missing.json')
check('rejects: missing field', rc == 2 and 'missing field: expected' in out, out)
rc, out = annotate(None, 'bad_json.json', raw='{not json')
check('rejects: invalid json', rc == 2, out)
rc, out = annotate(None, 'bad_list.json', raw='[1,2]')
check('rejects: not an object', rc == 2, out)
r = subprocess.run([sys.executable, str(SCRIPTS / 'annotate.py'), '--file', str(BASE / 'usage' / 'agent-usage.jsonl')], capture_output=True, text=True, env=dict(os.environ))
check('rejects: file outside inbox', r.returncode == 2 and 'inbox' in r.stdout, r.stdout)
check('only the valid annotation was appended', len((BASE / 'eval' / 'annotations.jsonl').read_text(encoding='utf-8').splitlines()) == 1)
rc, out = annotate(dict(GOODANN, run_agent_id='aaa111', outcome='disputed', verified='unclear'), 'ok2.json')
check('disputed/unclear accepted', rc == 0, out)
rc2, out2 = annotate(dict(GOODANN, run_agent_id='aaa111', outcome='disputed', verified='unclear'), 'ok2.json')
check('same file can be re-ingested but is a distinct append-only record', rc2 == 0 and len((BASE / 'eval' / 'annotations.jsonl').read_text(encoding='utf-8').splitlines()) == 3)

# ------------------------------------------------------------ guard-annotator.ps1
REALBOX = str(BASE).replace('\\', '/') + '/eval/'
PY = (str(SCRIPTS).replace('\\', '/')) + '/annotate.py'


def guard(agent, tool, **ti):
    inp = json.dumps({'agent_type': agent, 'tool_name': tool, 'tool_input': ti})
    r = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(GUARD)], input=inp, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stderr


tmpf = pathlib.Path(REALBOX + 'inbox/_guardtest_exists.json')
tmpf.write_text('{}', encoding='utf-8')
fake = BASE / 'fake_scripts'
fake.mkdir()
(fake / 'annotate.py').write_text('print("not the real script")\n', encoding='utf-8')
FAKE = str(fake).replace('\\', '/') + '/annotate.py'
try:
    for agent in ('annotator', 'agent-eval:annotator'):
        W = lambda p: guard(agent, 'Write', file_path=p, content='{}')
        B = lambda c: guard(agent, 'Bash', command=c)
        check('guard[%s]: write new inbox json allowed' % agent, W(REALBOX + 'inbox/abc-new.json')[0] == 0)
        check('guard[%s]: write with backslashes allowed' % agent, W(REALBOX.replace('/', '\\') + 'inbox\\abc-new2.json')[0] == 0)
        for label, p in {'overwrite existing': REALBOX + 'inbox/_guardtest_exists.json', 'outside inbox': REALBOX + 'annotations.jsonl', 'settings': 'C:/Users/x/.claude/settings.json',
                         'traversal': REALBOX + 'inbox/../x.json', 'non-json': REALBOX + 'inbox/x.sh', 'subdir': REALBOX + 'inbox/sub/x.json',
                         'space in name': REALBOX + 'inbox/a b.json', 'relative': 'inbox/x.json'}.items():
            check('guard[%s]: write blocked: %s' % (agent, label), W(p)[0] == 2)
        ok = 'python %s --file %sinbox/_guardtest_exists.json' % (PY, REALBOX)
        check('guard[%s]: annotate command allowed' % agent, B(ok)[0] == 0)
        check('guard[%s]: quoted paths allowed' % agent, B('python "%s" --file "%sinbox/_guardtest_exists.json"' % (PY, REALBOX))[0] == 0)
        check('guard[%s]: python3 allowed' % agent, B(ok.replace('python ', 'python3 ', 1))[0] == 0)
        for label, c in {'nonexistent file': 'python %s --file %sinbox/nope.json' % (PY, REALBOX), 'chained': ok + ' && cat /etc/passwd', 'piped': ok + ' | head',
                         'same name, different content': 'python %s --file %sinbox/_guardtest_exists.json' % (FAKE, REALBOX),
                         'other script': 'python C:/evil.py --file %sinbox/_guardtest_exists.json' % REALBOX, 'other flag': ok + ' --x',
                         'outside inbox': 'python %s --file C:/Windows/win.ini' % PY, 'subshell': 'python %s --file $(whoami).json' % PY,
                         'rm': 'rm -rf C:/Users', 'cat settings': 'cat C:/Users/x/.claude/settings.json', 'empty': ''}.items():
            check('guard[%s]: bash blocked: %s' % (agent, label), B(c)[0] == 2)
    check('guard: other agents unaffected (write)', guard('verification-runner', 'Write', file_path='C:/anything.txt')[0] == 0)
    check('guard: other agents unaffected (bash)', guard('bulk-reader', 'Bash', command='ls')[0] == 0)
    check('guard: main thread unaffected', guard('', 'Bash', command='rm -rf x')[0] == 0)
    check('guard: annotator Read passes through', guard('annotator', 'Read', file_path='C:/x.txt')[0] == 0)
finally:
    tmpf.unlink()

# ------------------------------------------------------------ agent_eval: queue / judge / review / export / report
state = ev.load_state()
q = [c[0] for c in ev.candidates(state, 0.0)]
check('queue: annotated and flagged runs, oldest first; info-only and clean excluded', q == ['bbb222', 'aaa111'], q)
check('queue: sampling is deterministic', [c[0] for c in ev.candidates(state, 1.0)] == [c[0] for c in ev.candidates(state, 1.0)])
check('queue: sample 1.0 adds clean runs', {'ccc333', 'ddd444'} <= {c[0] for c in ev.candidates(state, 1.0)})
check('queue: sample 0 adds none', len(ev.candidates(state, 0.0)) == 2)

stub = BASE / 'stub_judge.py'
stub.write_text('import sys,json\nsys.stdin.read()\nprint("```json")\nprint(json.dumps({"verdict":"fail","confidence":0.8,"issues":[{"code":"wrong_count","severity":"medium","claim_in_answer":"3 tables","what_is_true":"4 tables","evidence":"schema.sql:1"}],"violated_rules":["Counts must reconcile."],"expected_behaviour":"List 4 tables.","checked":["count"]}))\nprint("```")\n', encoding='utf-8')
bad_stub = BASE / 'bad_stub.py'
bad_stub.write_text('import sys\nsys.stdin.read()\nprint("I cannot do that")\n', encoding='utf-8')


class NS:
    def __init__(self, **k):
        self.__dict__.update(k)


buf = io.StringIO()
old = sys.stdout
sys.stdout = buf
ev.cmd_judge(NS(sample=0.0, only_flagged=False, limit=10, dry_run=True, model='m', judge_cmd=None))
ev.cmd_judge(NS(sample=0.0, only_flagged=False, limit=10, dry_run=False, model='m', judge_cmd='"%s" "%s"' % (sys.executable, bad_stub)))
nothing_recorded = ev.read_jsonl(ev.JUD) == []
ev.cmd_judge(NS(sample=0.0, only_flagged=False, limit=1, dry_run=False, model='m', judge_cmd='"%s" "%s"' % (sys.executable, stub)))
sys.stdout = old
txt = buf.getvalue()
check('judge: dry run writes nothing and lists candidates', 'would judge bbb222' in txt, txt)
check('judge: invalid judge output is not recorded', 'FAILED' in txt and nothing_recorded)
juds = ev.read_jsonl(ev.JUD)
check('judge: valid verdict recorded once (limit 1)', len(juds) == 1 and juds[0]['verdict'] == 'fail' and juds[0]['source'] == 'judge' and juds[0]['judge_prompt_version'] == 'judge-v1', juds)
check('judge: prompt contains data markers and run facts', 'DATA from a recorded run' in (ev.build_judge_prompt(state[0]['bbb222'], state[1]['bbb222']) or '') and 'Counts must reconcile' in ev.build_judge_prompt(state[0]['bbb222'], state[1]['bbb222']))
check('judge: prompt carries hook flags as leads', 'reconciliation_mismatch' in ev.build_judge_prompt(state[0]['aaa111'], []))
buf = io.StringIO(); sys.stdout = buf
ev.cmd_judge(NS(sample=0.0, only_flagged=False, limit=10, dry_run=True, model='m', judge_cmd=None))
sys.stdout = old
check('judge: judged run no longer a to-do', 'bbb222' not in buf.getvalue() and 'aaa111' in buf.getvalue(), buf.getvalue())

# transcript integrity warning
prompt, answer, ok = ev.transcript_parts(state[0]['bbb222'])
check('transcript parts read on demand', prompt == 'list tables' and answer.startswith('Answer text') and ok)
(BASE / 'tx_aaa111.jsonl').write_text((BASE / 'tx_aaa111.jsonl').read_text(encoding='utf-8') + '\n', encoding='utf-8')
check('tampered transcript detected', ev.transcript_parts(state[0]['aaa111'])[2] is False)

# review (scripted answers)
answers = iter(['c', 'wrong_count', 'high', '', '', 'checked by operator',   # bbb222: confirm with defaults for expected/fix
                'r', 'agent was right'])                                       # aaa111: reject
buf = io.StringIO(); sys.stdout = buf
ev.cmd_review(NS(sample=0.0, limit=10), inp=lambda msg='': next(answers))
sys.stdout = old
revs = ev.read_jsonl(ev.REV)
check('review: two decisions saved', [r['decision'] for r in revs] == ['confirmed_failure', 'false_alarm'], revs)
check('review: defaults taken from annotation', revs[0]['expected'].startswith('List all 4 tables') and revs[0]['suggested_fix'].startswith('Count CREATE') and revs[0]['severity'] == 'high')
check('review: provenance fields', revs[0]['source'] == 'human' and revs[0]['reviewer'] and revs[0]['queued_because'])
check('review: reviewed cases leave the queue', ev.candidates(ev.load_state(), 0.0) == [])
answers = iter(['o'])
buf = io.StringIO(); sys.stdout = buf
ev.cmd_review(NS(sample=1.0, limit=1), inp=lambda msg='': next(answers))
sys.stdout = old
check('review: sampled clean case can be confirmed ok', ev.read_jsonl(ev.REV)[-1]['decision'] == 'confirmed_ok')
answers = iter(['s', 'q'])
buf = io.StringIO(); sys.stdout = buf
ev.cmd_review(NS(sample=1.0, limit=5), inp=lambda msg='': next(answers))
sys.stdout = old
check('review: skip and quit save nothing', len(ev.read_jsonl(ev.REV)) == 3)

# export + report
out = BASE / 'neg.jsonl'
ev.cmd_export(NS(include_content=False, positives=False, out=str(out)))
cases = [json.loads(l) for l in out.read_text(encoding='utf-8').splitlines()]
check('export: only confirmed failures, references only', len(cases) == 1 and cases[0]['case_id'] == 'bbb222' and 'agent_answer' not in cases[0] and cases[0]['label'] == 'negative', cases)
check('export: provenance lists every label source', set(cases[0]['label_provenance']) >= {'hook_flags', 'annotations', 'judgements', 'human_review', 'reviewer'})
ev.cmd_export(NS(include_content=True, positives=False, out=str(out)))
c2 = json.loads(out.read_text(encoding='utf-8').splitlines()[0])
check('export: content embedded only on request', c2['task_prompt'] == 'list tables' and c2['agent_answer'].startswith('Answer text') and c2['content_hash_matches'] is True)
buf = io.StringIO(); sys.stdout = buf
ev.cmd_report(NS())
ev.cmd_status(NS(sample=0.0))
sys.stdout = old
check('report: shows agent, code and rule fix', 'schema-reader' in buf.getvalue() and 'wrong_count x1' in buf.getvalue() and 'rule fix -> Count CREATE' in buf.getvalue(), buf.getvalue())

# calibration with a stub that detects everything -> perfect detection but all false alarms (shows the metric works)
ev.EVAL = BASE / 'eval'
with open(ev.EVAL / 'calibration.jsonl', 'w', encoding='utf-8') as f:
    f.write(json.dumps({'id': 'good1', 'agent_type': 'schema-reader', 'prompt': 'p', 'answer': 'a', 'expected': 'pass'}) + '\n')
    f.write(json.dumps({'id': 'bad1', 'agent_type': 'schema-reader', 'prompt': 'p', 'answer': 'a', 'expected': 'fail', 'defect': 'planted'}) + '\n')
buf = io.StringIO(); sys.stdout = buf
ev.cmd_calibrate(NS(model='m', workers=2, judge_cmd='"%s" "%s"' % (sys.executable, stub)))
sys.stdout = old
check('calibrate: counts detection and false alarms', 'detection of planted failures: 1/1' in buf.getvalue() and 'false alarms on good outputs: 1/1' in buf.getvalue(), buf.getvalue())

print('%d/%d passed' % (passed, passed + failed))
sys.exit(1 if failed else 0)
