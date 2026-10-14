"""guard-secret-leak.sh (POSIX sh, awk): the hand-back redaction must leave TypeScript generic types and plural label keys alone (issue #2) and still redact real
secrets. The PowerShell version is covered by test_guard_secret_leak.py. Run: python test_guard_secret_leak_sh.py"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-guards' / 'scripts' / 'guard-secret-leak.sh'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='sgsh_'))
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def handback(message):
    """-> the (possibly rewritten) message, or None when the hook let it through unchanged"""
    inp = {'session_id': 's1', 'transcript_path': str(TMP / 's1.jsonl'), 'tool_name': 'SubagentHandback', 'tool_input': {'message': message},
           'hook_event_name': 'PreToolUse', 'agent_id': 'agx', 'agent_type': 'code-explorer'}
    p = subprocess.run(['sh', str(HOOK)], input=json.dumps(inp), capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, SECRET_GUARD_AUDIT=str(TMP / 'audit.jsonl')))
    if p.returncode != 0:
        return f'EXIT {p.returncode}: {p.stderr[:200]}'
    if not p.stdout.strip():
        return None
    return json.loads(p.stdout.strip().splitlines()[-1])['hookSpecificOutput']['updatedInput']['message']


SAFE = {
    'record type after a secret-named constant': "const SECRET_LABELS: Record<string, string> = { a: 'b' };",
    'map and array types after token-named fields': 'TOKEN_MAP: Map<string, number>; credentialsCache: Array<string>;',
    'promise type': 'async function getToken(): Promise<void> { } const authKeyFn: Promise<string> = x;',
    'plural label and name keys': 'token_labels: someValueHere and secretNames: anotherValue',
    'jenkins credential reference': "NPM_TOKEN = credentials('npm-publish-token')",
    'env reference': 'password = os.environ["DB_PASSWORD"]',
}
SECRET = 'Zq8' + 'Lm2Vx9Tp4Rw7'   # not a real credential; assembled so this file holds no secret-shaped literal


def main():
    if not shutil.which('sh'):
        print('SKIP: needs a POSIX sh and awk')
        return
    for name, msg in SAFE.items():
        out = handback(msg)
        check(f'[sh] not redacted: {name}', out is None, str(out))
    out = handback(f'password = {SECRET} and nothing else')
    check('[sh] a real password assignment is still redacted', out is not None and SECRET not in out and 'redacted' in out, str(out))
    out = handback(f'token: {SECRET}')
    check('[sh] a real token assignment is still redacted', out is not None and SECRET not in out, str(out))
    print(f'{sum(results)}/{len(results)} passed')
    shutil.rmtree(TMP, ignore_errors=True) if TMP.name.startswith('sgsh_') and TMP.parent == pathlib.Path(tempfile.gettempdir()) else None
    sys.exit(0 if all(results) else 1)


main()
