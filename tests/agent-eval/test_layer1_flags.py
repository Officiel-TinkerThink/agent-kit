"""Layer 1 tests: run subagent-usage-log.ps1 on synthetic transcripts with planted failures and check the recorded flags.
Run: python test_layer1_flags.py   (uses a temp log via AGENT_USAGE_LOG; never touches the real log)"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from capability import run_capability   # the OS adapter picks the implementation (PowerShell on Windows, sh on Linux)

HOOK = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-eval' / 'scripts' / 'subagent-usage-log.ps1'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='l1test_'))
REAL = TMP / 'real.sql'
REAL.write_text('\n'.join('line %d' % i for i in range(1, 11)), encoding='utf-8')
REALP = REAL.as_posix()
passed = failed = 0


def transcript(output, handback=True, blocked=False, usage_twice=False):
    ts = '2026-10-12T10:00:0%d.000Z'
    rows = [{'type': 'user', 'timestamp': ts % 0, 'message': {'role': 'user', 'content': 'do the task'}}]
    use = {'input_tokens': 2, 'output_tokens': 100, 'cache_read_input_tokens': 1000, 'cache_creation_input_tokens': 500}
    rows.append({'type': 'assistant', 'timestamp': ts % 1, 'uuid': 'a', 'message': {'id': 'm1', 'model': 'claude-haiku-5-5', 'usage': use, 'content': [{'type': 'thinking', 'thinking': ''}]}})
    if usage_twice:
        rows.append({'type': 'assistant', 'timestamp': ts % 2, 'uuid': 'b', 'message': {'id': 'm1', 'model': 'claude-haiku-5-5', 'usage': use, 'content': [{'type': 'tool_use', 'name': 'Read', 'input': {}}]}})
    if blocked:
        rows.append({'type': 'user', 'timestamp': ts % 3, 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'x', 'is_error': True, 'content': 'BLOCKED: nope'}]}})
    if handback:
        rows.append({'type': 'assistant', 'timestamp': ts % 5, 'uuid': 'c', 'message': {'id': 'm2', 'model': 'claude-haiku-5-5', 'usage': use, 'content': [{'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': output}}]}})
    p = TMP / ('t%d.jsonl' % len(list(TMP.glob('t*.jsonl'))))
    p.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    return p


def run(agent, output, **kw):
    tp = transcript(output, **kw)
    inp = TMP / 'in.json'
    inp.write_text(json.dumps({'session_id': 's', 'agent_id': 'agent%d' % len(list(TMP.glob('t*.jsonl'))), 'agent_type': agent, 'effort': {'level': 'low'},
                               'cwd': str(TMP), 'agent_transcript_path': str(tp)}), encoding='utf-8')
    log = TMP / 'log.jsonl'
    if log.exists():
        log.unlink()
    env = dict(os.environ, AGENT_USAGE_LOG=str(log), AGENT_KIT_DATA=str(TMP / 'kit'))   # never write hook errors or audit into the real data folder
    run_capability(HOOK, '-SelfTestInput', str(inp), env=env, check=True, capture_output=True, timeout=60)
    return json.loads(log.read_text(encoding='utf-8').splitlines()[-1]), log.read_text(encoding='utf-8')


def check(name, cond, extra=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print('FAIL', name, extra)


def codes(rec, sev=None):
    return sorted(f['code'] for f in rec['flags'] if sev is None or f['sev'] == sev)


GOOD = 'Table users (%s:3)\nCoverage: read 1 file.\nReconciliation: expected 4 / listed 4.' % REALP
r, _ = run('schema-reader', GOOD)
check('clean output has no fail/warn', not r['flagged'] and codes(r) == [], codes(r))
check('schema v2 fields', r['schema'] == 'agent-usage/2' and r['transcript_sha256'] and r['output_chars'] == len(GOOD))
check('tokens', r['tokens']['output'] == 200 and r['tokens']['cache_read'] == 2000 and r['api_calls'] == 2, r['tokens'])

r, _ = run('schema-reader', GOOD, usage_twice=True)
check('usage deduplicated by message id', r['tokens']['output'] == 200 and r['api_calls'] == 2, r['tokens'])

r, _ = run('schema-reader', 'x\nCoverage: a\nReconciliation: ok\n' + 'C:/no/such/dir/file.sql:12')
check('citation file missing', 'citation_file_missing' in codes(r, 'fail') and r['flagged'], codes(r))
r, _ = run('schema-reader', 'x\nCoverage: a\nReconciliation: ok\n%s:99' % REALP)
check('citation line out of range', 'citation_line_out_of_range' in codes(r, 'fail'), codes(r))
r, _ = run('schema-reader', 'x\nCoverage: a\nReconciliation: ok\n%s:10 and %s:1' % (REALP, REALP))
check('boundary lines valid', not r['flagged'], codes(r))
r, _ = run('schema-reader', 'x\nCoverage: a\nReconciliation: ok\nrelative/file.sql:9999 and 0001.sql:5')
check('relative citations are not judged', not r['flagged'], codes(r))

canaries = {'aws': 'AKIAABCDEFGHIJKLMNOP', 'sonar': 'squ_' + 'a1b2c3d4e5' * 4, 'ghp': 'ghp_' + 'A' * 36, 'pem': '-----BEGIN RSA PRIVATE KEY-----',
            'url': 'postgres://svc:Hunter2Pass@db:5432/x', 'pw': 'password = Sup3rS3cretValue'}
for k, v in canaries.items():
    r, raw = run('bulk-reader', 'The config contains ' + v + ' near the top of the file')
    check('secret ' + k, 'secret_pattern' in codes(r, 'fail'), codes(r))
    secret_core = v.split('//')[-1].split('= ')[-1]
    check('secret value not logged ' + k, secret_core not in raw, 'value leaked into the log')
r, _ = run('bulk-reader', 'password handling is described in section 3; the password field is hashed')
check('word password alone is fine', 'secret_pattern' not in codes(r), codes(r))

r, _ = run('advisory-collector', 'This version has no known vulnerabilities.')
check('forbidden phrase flagged', 'forbidden_phrase' in codes(r, 'warn'), codes(r))
r, _ = run('advisory-collector', 'foo 1.0 is safe to upgrade.')
check('safe to upgrade flagged', 'forbidden_phrase' in codes(r, 'warn'), codes(r))
r, _ = run('advisory-collector', 'None listed in OSV. This does not mean the version has no vulnerabilities, and I never say a version is safe.')
check('negated phrasing not flagged', 'forbidden_phrase' not in codes(r), codes(r))
r, _ = run('advisory-collector', 'Compliance: not determinable. The system is not safe to assume compliant.')
check('"not safe to" not flagged', 'forbidden_phrase' not in codes(r), codes(r))

r, _ = run('contract-reader', 'Coverage: ok\nReconciliation: expected 20 / listed 19')
check('reconciliation mismatch', 'reconciliation_mismatch' in codes(r, 'fail'), codes(r))
r, _ = run('contract-reader', 'Coverage: ok\nReconciliation: expected 20 / listed 20; paths expected 11 / listed 11')
check('reconciliation match', not r['flagged'], codes(r))
r, _ = run('schema-reader', 'tables: users, orders (plenty of text here)\nCoverage: yes')
check('footer Reconciliation missing', 'footer_missing' in codes(r, 'warn'), codes(r))
r, _ = run('schema-reader', 'tables: users, orders (plenty of text here)\nReconciliation: expected 2 / listed 2')
check('footer Coverage missing', 'footer_missing' in codes(r, 'warn'), codes(r))
r, _ = run('schema-reader', '{"users": ["id", "email"]}')
check('JSON-only answer exempt from footers', not r['flagged'], codes(r))
r, _ = run('schema-reader', '```json\n{"users": ["id", "email"]}\n```')
check('fenced JSON valid', not r['flagged'], codes(r))
r, _ = run('schema-reader', '{"users": ["id", "email"')
check('invalid JSON flagged', 'json_invalid' in codes(r, 'fail'), codes(r))
r, _ = run('bulk-reader', 'A plain answer with enough text to count as an answer.')
check('plain answer from non-footer agent is clean', not r['flagged'], codes(r))

r, _ = run('bulk-reader', '', handback=False)
check('no handback', 'no_final_answer' in codes(r, 'fail') and r['flagged'], codes(r))
r, _ = run('bulk-reader', 'ok')
check('empty/short output', 'empty_output' in codes(r, 'fail'), codes(r))
r, _ = run('bulk-reader', 'A plain answer with enough text to count as an answer.', blocked=True)
check('blocked tool call is info only', codes(r, 'info') == ['guard_blocked'] and not r['flagged'], codes(r))
r, _ = run('bulk-reader', 'x' * 21000)
check('oversized output warn', 'oversized_output' in codes(r, 'warn'), codes(r))

# secret-guard audit events surface as flags (kinds and counts only)
sg = TMP / 'sg.jsonl'
sg.write_text(json.dumps({'agent_id': 'agent%d' % (len(list(TMP.glob('t*.jsonl'))) + 1), 'action': 'redacted', 'count': 2, 'kinds': ['aws_access_key', 'url_credential'], 'tool': 'SubagentHandback'}) + '\n', encoding='utf-8')
os.environ['SECRET_GUARD_AUDIT'] = str(sg)
r, _ = run('bulk-reader', 'A plain answer with enough text to count as an answer.')
check('secret_redacted flag from audit', 'secret_redacted' in codes(r, 'warn') and r['flagged'], codes(r))
sg.write_text(json.dumps({'agent_id': 'agent%d' % (len(list(TMP.glob('t*.jsonl'))) + 1), 'action': 'blocked', 'count': 1, 'kinds': ['github_token'], 'tool': 'WebFetch'}) + '\n', encoding='utf-8')
r, _ = run('bulk-reader', 'A plain answer with enough text to count as an answer.')
check('secret_exfil_blocked flag from audit', 'secret_exfil_blocked' in codes(r, 'fail'), codes(r))
sg.write_text(json.dumps({'agent_id': 'someone-else', 'action': 'redacted', 'count': 1, 'kinds': ['x'], 'tool': 'SubagentHandback'}) + '\n', encoding='utf-8')
r, _ = run('bulk-reader', 'A plain answer with enough text to count as an answer.')
check('other agents audit events are ignored', 'secret_redacted' not in codes(r), codes(r))
del os.environ['SECRET_GUARD_AUDIT']

# the hook must never fail on garbage input
for bad in ['', 'not json', '{"agent_id": "z", "agent_transcript_path": "C:/nope.jsonl", "agent_type": "x"}']:
    inp = TMP / 'bad.json'
    inp.write_text(bad, encoding='utf-8')
    p = run_capability(HOOK, '-SelfTestInput', str(inp),
                       env=dict(os.environ, AGENT_USAGE_LOG=str(TMP / 'bad.log'), AGENT_KIT_DATA=str(TMP / 'kit')), capture_output=True, timeout=60)
    check('fail-open on bad input %r' % bad[:20], p.returncode == 0)
last = (TMP / 'bad.log').read_text(encoding='utf-8').splitlines()[-1] if (TMP / 'bad.log').exists() else ''
check('missing transcript still yields a flagged record', bool(last) and 'no_final_answer' in last)

print('%d/%d passed' % (passed, passed + failed))
sys.exit(1 if failed else 0)
