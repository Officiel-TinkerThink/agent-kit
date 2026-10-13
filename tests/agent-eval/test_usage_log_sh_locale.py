"""The POSIX usage-log hook must write its run record whatever the user's locale is.

On Ubuntu the shell has a UTF-8 locale (en_US.UTF-8, C.UTF-8). gawk 5 rejects the byte-range regexes of the
checks program there ("Invalid collation character"), the checks stage exited 1, and the hook logged
"run record not written: output checks failed" for every run: no usage log, so the annotator could not find any
run. Run: python test_usage_log_sh_locale.py   (POSIX only; uses a throwaway log and data folder)"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

if sys.platform == 'win32' or not shutil.which('sh') or not shutil.which('awk'):
    print('SKIP: needs a POSIX sh and awk')
    sys.exit(0)

HOOK = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-eval' / 'scripts' / 'subagent-usage-log.sh'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='ullocale_'))
passed = failed = 0


def check(name, cond, extra=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print('FAIL', name, extra)


def utf8_locales():
    out = subprocess.run(['locale', '-a'], capture_output=True, text=True).stdout.split() if shutil.which('locale') else []
    return [l for l in out if l.lower().replace('-', '').endswith('utf8')][:3]


def transcript(answer):
    ts = '2026-10-14T10:00:0%d.000Z'
    use = {'input_tokens': 2, 'output_tokens': 100, 'cache_read_input_tokens': 1000, 'cache_creation_input_tokens': 500}
    rows = [{'type': 'user', 'timestamp': ts % 0, 'message': {'role': 'user', 'content': 'do the task'}},
            {'type': 'assistant', 'timestamp': ts % 1, 'uuid': 'a', 'message': {'id': 'm1', 'model': 'claude-haiku-5-5', 'usage': use, 'content': [{'type': 'thinking', 'thinking': ''}]}},
            {'type': 'assistant', 'timestamp': ts % 2, 'uuid': 'b', 'message': {'id': 'm2', 'model': 'claude-haiku-5-5', 'usage': use,
                                                                              'content': [{'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': answer}}]}}]
    p = TMP / 't.jsonl'
    p.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    return p


def run(locale, answer):
    tp = transcript(answer)
    inp = TMP / 'in.json'
    inp.write_text(json.dumps({'session_id': 's', 'agent_id': 'agentL', 'agent_type': 'repo-scout', 'effort': {'level': 'low'},
                               'cwd': str(TMP), 'agent_transcript_path': str(tp)}), encoding='utf-8')
    log = TMP / 'log.jsonl'
    if log.exists():
        log.unlink()
    data = TMP / 'kit'
    env = {k: v for k, v in os.environ.items() if not k.startswith('LC_') and k != 'LANG'}
    env.update(LC_ALL=locale, AGENT_USAGE_LOG=str(log), AGENT_KIT_DATA=str(data))
    p = subprocess.run(['sh', str(HOOK), '-SelfTestInput', str(inp)], env=env, capture_output=True, text=True, timeout=60)
    errors = (data / 'hook-errors.log').read_text(encoding='utf-8') if (data / 'hook-errors.log').exists() else ''
    return p, log, errors


ANSWER = 'Hasil: 12,5 L — selesai ✓ (src/app.py:3)\nCoverage: read 1 file.'
for loc in ['C'] + utf8_locales():
    p, log, errors = run(loc, ANSWER)
    check('[%s] hook exits 0' % loc, p.returncode == 0, p.stderr[-200:])
    check('[%s] no hook error logged' % loc, 'output checks failed' not in errors, errors[-300:])
    rec = json.loads(log.read_text(encoding='utf-8').splitlines()[-1]) if log.exists() and log.read_text(encoding='utf-8').strip() else None
    check('[%s] a run record was written' % loc, rec is not None)
    if rec:
        check('[%s] record names the run' % loc, rec['agent_id'] == 'agentL' and rec['agent_type'] == 'repo-scout', rec)
if not utf8_locales():
    print('NOTE: no UTF-8 locale installed here; only the C locale was exercised')

print('passed %d failed %d' % (passed, failed))
sys.exit(1 if failed else 0)
