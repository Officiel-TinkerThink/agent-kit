"""Tests for kit-policy.ps1 (/kit-allow: browser hosts) and kit-doctor.ps1 (/kit-doctor). Run: python test_kit_tools.py"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from capability import run_capability   # the OS adapter picks the implementation (PowerShell on Windows, sh on Linux)

PLUGINS = pathlib.Path(__file__).resolve().parents[2] / 'plugins'
POLICY = PLUGINS / 'agent-guards' / 'scripts' / 'kit-policy.ps1'
DOCTOR = PLUGINS / 'agent-guards' / 'scripts' / 'kit-doctor.ps1'
BROWSER_GUARD = PLUGINS / 'agent-guards' / 'scripts' / 'guard-browser.ps1'
results = []


def kit():
    return pathlib.Path(tempfile.mkdtemp(prefix='kittools_')).resolve()


def ps(script, k, *args, stdin=None):
    env = dict(os.environ, AGENT_KIT_DATA=str(k).replace('\\', '/'))
    p = run_capability(script, *args, input=stdin, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr


def check(name, passed, extra=''):
    results.append(bool(passed))
    print(('PASS' if passed else 'FAIL'), name, extra if not passed else '')


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def changes(k):
    f = k / 'audit' / 'policy-changes.jsonl'
    return [json.loads(x) for x in f.read_text(encoding='utf-8-sig').splitlines() if x.strip()] if f.exists() else []


def hosts_policy(k, hosts):
    (k / 'browser-policy.json').write_text(json.dumps({'allowedHosts': hosts}), encoding='utf-8')


def main():
    # ---- kit-policy: add-host
    k = kit()
    check('add-host: refused when no allowedHosts exist (would restrict)', ps(POLICY, k, '-Action', 'add-host', '-HostName', 'docs.example.com', '-Reason', 'r')[0] == 1)
    hosts_policy(k, ['127.0.0.1'])
    code, _, err = ps(POLICY, k, '-Action', 'add-host', '-HostName', 'Docs.Example.com', '-Reason', 'vendor docs')
    hosts = json.loads((k / 'browser-policy.json').read_text(encoding='utf-8-sig'))['allowedHosts']
    check('add-host: appended lower-cased', code == 0 and hosts == ['127.0.0.1', 'docs.example.com'], err)
    ch = changes(k)
    check('add-host: change recorded with hashes and reason', len(ch) == 1 and ch[0]['file'] == 'browser-policy.json' and ch[0]['after_sha256'] == sha(k / 'browser-policy.json') and ch[0]['reason'] == 'vendor docs')
    code, out, _ = ps(POLICY, k, '-Action', 'add-host', '-HostName', 'docs.example.com', '-Reason', 'again')
    check('add-host: duplicate is a no-op', code == 0 and 'Already allowed' in out and len(changes(k)) == 1)
    code, _, _ = ps(POLICY, k, '-Action', 'add-host', '-HostName', 'wiki.example.com', '-Reason', 'second')
    ch = changes(k)
    check('add-host: second change chains onto the first hash', code == 0 and len(ch) == 2 and ch[1]['before_sha256'] == ch[0]['after_sha256'])
    check('add-host: reason required', ps(POLICY, k, '-Action', 'add-host', '-HostName', 'x.example.com')[0] == 1)
    for bad in ('http://x.test', 'x.test/path', '*.test', 'a..b', 'x:8080'):
        check(f'add-host: refuses {bad!r}', ps(POLICY, k, '-Action', 'add-host', '-HostName', bad, '-Reason', 'r')[0] == 1)
    kb = kit()
    (kb / 'browser-policy.json').write_text('{broken', encoding='utf-8')
    code, _, _ = ps(POLICY, kb, '-Action', 'add-host', '-HostName', 'a.example.com', '-Reason', 'r')
    check('add-host: invalid JSON policy is refused, not overwritten', code == 1 and (kb / 'browser-policy.json').read_text() == '{broken')
    check('commands are not managed here any more', ps(POLICY, kit(), '-Action', 'add-command', '-Command', 'python a.py', '-Reason', 'r')[0] != 0)

    # ---- a blocked host is logged, listed, approved, then allowed
    k = kit()
    hosts_policy(k, ['127.0.0.1'])
    payload = json.dumps({'agent_type': 'haiku-delegation:browser-explorer', 'session_id': 's', 'tool_name': 'mcp__claude-in-chrome__navigate', 'tool_input': {'url': 'https://docs.example.com/x', 'tabId': 1}})
    code, _, err = ps(BROWSER_GUARD, k, stdin=payload)
    ps(BROWSER_GUARD, k, stdin=payload)
    code2, out, _ = ps(POLICY, k, '-Action', 'list-blocked')
    check('browser: host block exits 2, points at kit-allow, and is listed once with count 2', code == 2 and 'kit-allow' in err and '[host] docs.example.com' in out and 'x2' in out, out + err)
    ps(POLICY, k, '-Action', 'add-host', '-HostName', 'docs.example.com', '-Reason', 'vendor docs')
    check('browser: allowed after approval', ps(BROWSER_GUARD, k, stdin=payload)[0] == 0)
    code, out, _ = ps(POLICY, k, '-Action', 'list-blocked')
    check('browser: approved host no longer pending', 'docs.example.com' not in out, out)
    check('browser: audit carries the policy hash only for operator decisions (explorer unaudited)', not (k / 'audit' / 'browser-actions.jsonl').exists())

    # ---- kit-doctor
    k = kit()
    code, out, _ = ps(DOCTOR, k)
    check('doctor: clean data folder has no FAIL', code == 0 and 'Summary: 0 FAIL' in out, out)
    check('doctor: reports the resolved KIT_DATA', str(k).replace('\\', '/') in out)

    k = kit()
    (k / 'browser-policy.json').write_text('{nope', encoding='utf-8')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: invalid policy is a FAIL', code == 1 and '[FAIL] browser-policy.json' in out, out)

    k = kit()
    (k / 'audit').write_text('file, not folder')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: unwritable audit folder is a FAIL', code == 1 and '[FAIL] writable' in out, out)

    k = kit()
    hosts_policy(k, ['127.0.0.1'])
    code, out, _ = ps(DOCTOR, k)
    check('doctor: policy never changed via kit-allow is flagged', '[WARN] browser-policy.json integrity' in out and 'never changed' in out, out)
    ps(POLICY, k, '-Action', 'add-host', '-HostName', 'docs.example.com', '-Reason', 'r')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: managed policy matches its change record', '[OK] browser-policy.json integrity' in out, out)
    p = k / 'browser-policy.json'
    data = json.loads(p.read_text(encoding='utf-8-sig'))
    data['allowedHosts'].append('evil.example.com')
    p.write_text(json.dumps(data), encoding='utf-8')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: hand edit detected as drift', '[WARN] browser-policy.json integrity' in out and 'edited outside' in out, out)

    k = kit()
    (k / 'verification-policy.json').write_text('{"extraCommands": []}', encoding='utf-8')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: leftover verification-policy.json reported as obsolete', '[WARN] verification-policy.json' in out and 'obsolete' in out, out)

    k = kit()
    (k / 'hook-errors.log').write_text('2000-01-01T00:00:00.0000000+00:00 old thing\n', encoding='utf-8')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: old hook errors are not flagged', '[OK] hook-errors.log' in out, out)
    (k / 'hook-errors.log').write_text(datetime.now(timezone.utc).isoformat() + ' guard-browser audit write failed: test\n', encoding='utf-8')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: fresh hook error is a WARN', '[WARN] hook-errors.log' in out, out)

    k = kit()
    (k / 'audit').mkdir()
    (k / 'audit' / 'blocked-requests.jsonl').write_text(json.dumps({'ts': datetime.now(timezone.utc).isoformat(), 'kind': 'host', 'value': 'x.example.com', 'agent': 'a'}) + '\n', encoding='utf-8')
    code, out, _ = ps(DOCTOR, k)
    check('doctor: pending blocked request pointed at kit-allow', 'kit-allow' in out, out)

    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
