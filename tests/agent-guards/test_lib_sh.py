"""lib.sh (the shared POSIX sh helper every Linux hook uses): JSON reading/writing, KIT_DATA resolution, agent matching. Run: python test_lib_sh.py"""
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = ROOT / 'plugins' / 'agent-guards' / 'scripts' / 'lib.sh'
SH = shutil.which('sh')
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), ascii(name)[1:-1], '' if ok else ascii(extra))


def sh(snippet, env=None, stdin=None):
    script = f'KIT_SCRIPT_DIR="{LIB.parent.as_posix()}"\n. "$KIT_SCRIPT_DIR/lib.sh"\n{snippet}\n'
    p = subprocess.run([SH, '-c', script], capture_output=True, text=True, encoding='utf-8', env=env, input=stdin, timeout=60)
    return p.returncode, p.stdout, p.stderr


def get(doc, path):
    return sh('json_get "$J" "$P"', env={'J': doc, 'P': path, 'PATH': __import__('os').environ['PATH']})


def main():
    if not SH:
        check('sh is available', False)
    else:
        doc = json.dumps({
            'agent_type': 'verification-runner', 'n': 600, 'ok': True, 'nothing': None,
            'tool_input': {'command': 'cd /x && echo "q" \\ back\nline2\ttab é ✓ 😀', 'timeout': 600},
            'arr': [{'a': 1}, {'a': 'two'}, [7, 8]], 'empty_obj': {}, 'empty_arr': [], 'k.dot': 'no',
        })
        rc, out, _ = get(doc, 'agent_type')
        check('string value', (rc, out) == (0, 'verification-runner'), out)
        rc, out, _ = get(doc, 'tool_input.command')
        check('escapes, newline, tab, unicode and surrogate pair decoded', out == 'cd /x && echo "q" \\ back\nline2\ttab é ✓ 😀', repr(out))
        check('number', get(doc, 'n')[1] == '600')
        check('boolean', get(doc, 'ok')[1] == 'true')
        check('null', get(doc, 'nothing')[1] == 'null')
        check('array index', get(doc, 'arr.1.a')[1] == 'two')
        check('nested array', get(doc, 'arr.2.1')[1] == '8')
        rc, out, _ = get(doc, 'tool_input')
        check('object returned as raw JSON that parses', rc == 0 and json.loads(out)['timeout'] == 600, out)
        check('empty object and array', get(doc, 'empty_obj')[1] == '{}' and get(doc, 'empty_arr')[1] == '[]')
        rc, out, _ = get(doc, 'missing.path')
        check('missing path: exit 1, no output', rc == 1 and out == '', f'{rc} {out!r}')
        check('prefix of a key is not a match', get(doc, 'agent')[0] == 1)
        check('whitespace-heavy JSON', get('{ "a" :\n [ 1 ,\t{ "b" : "x y" } ] }', 'a.1.b')[1] == 'x y')
        rc, out, _ = sh('json_has "$J" tool_input.timeout && echo yes; json_has "$J" nope || echo no', env={'J': doc, 'PATH': __import__('os').environ['PATH']})
        check('json_has', out.split() == ['yes', 'no'], out)
        # json_str produces valid JSON string literals
        for raw in ['plain', 'quo"te', 'back\\slash', 'tab\there', 'new\nline', 'cr\rlf', 'é ✓', '']:
            rc, out, _ = sh('json_str "$T"', env={'T': raw, 'PATH': __import__('os').environ['PATH']})
            check(f'json_str round-trips {raw!r}', rc == 0 and json.loads(out) == raw, out)
        # kit_data resolution order
        base = {'PATH': __import__('os').environ['PATH'], 'HOME': '/home/u'}
        check('kit_data: AGENT_KIT_DATA wins, trailing slash removed', sh('kit_data', env=dict(base, AGENT_KIT_DATA='/d/kit/'))[1] == '/d/kit')
        check('kit_data: CLAUDE_CONFIG_DIR', sh('kit_data', env=dict(base, CLAUDE_CONFIG_DIR='/cfg'))[1] == '/cfg/agent-kit')
        rc, out, _ = sh('KIT_SCRIPT_DIR=/home/u/.claude-me/plugins/cache/agent-kit/agent-guards/0.1.11/scripts; kit_data', env=base)
        check('kit_data: derived from the plugin cache path', out == '/home/u/.claude-me/agent-kit', out)
        check('kit_data: HOME fallback', sh('kit_data', env=base)[1] == '/home/u/.claude/agent-kit')
        # agent_is / now_utc / append_line / sha256_of
        rc, out, _ = sh('agent_is "agent-guards:changelog-summarizer" changelog-summarizer && echo a; agent_is "x" changelog-summarizer || echo b; agent_is "changelog-summarizer" changelog-summarizer && echo c; agent_is "my-changelog-summarizer" changelog-summarizer || echo d')
        check('agent_is: exact and plugin-prefixed only', out.split() == ['a', 'b', 'c', 'd'], out)
        rc, out, _ = sh('now_utc')
        out = out.strip()
        check('now_utc is ISO-8601 UTC', len(out) == 24 and out.endswith('Z') and out[10] == 'T', out)
        d = pathlib.Path(__import__('tempfile').mkdtemp(prefix='libsh-'))
        f = (d / 'sub' / 'a.log').as_posix()
        rc, out, _ = sh(f'append_line "{f}" one; append_line "{f}" two; sha256_of "{f}"')
        check('append_line creates the folder and appends lines', (d / 'sub' / 'a.log').read_text() == 'one\ntwo\n')
        import hashlib
        check('sha256_of matches', out.strip() == hashlib.sha256(b'one\ntwo\n').hexdigest(), out)
        check('sha256_of of a missing file is empty', sh('sha256_of /nonexistent/x')[1] == '')
        shutil.rmtree(d, ignore_errors=True)
    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
