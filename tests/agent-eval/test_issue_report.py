"""/agent-eval:report-issue (issue-report.sh and issue-report.ps1): the draft holds only sanitized, aggregated evidence, both tools write the same draft,
nothing is sent without `submit`, and `submit` is limited to drafts in the reports folder. gh is always a stub (AGENT_KIT_GH); no test talks to GitHub.
Run: python test_issue_report.py   (temp data folders only)"""
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'agent-eval' / 'scripts'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='issuereport_'))
results = []
WIN = sys.platform == 'win32'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)   # one clock for every fixture, so both tools see the same timestamps


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    out = {}
    if shutil.which('sh'):
        out['sh'] = ['sh', str(SCRIPTS / 'issue-report.sh')]
    ps = (shutil.which('powershell.exe') or shutil.which('powershell')) if WIN else shutil.which('pwsh')   # not the Windows powershell.exe that WSL exposes through interop
    if ps:
        out['ps1'] = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / 'issue-report.ps1')]
    return out


def make_stub(kind):
    d = TMP / f'stub-{kind}'
    d.mkdir(parents=True, exist_ok=True)
    if kind == 'ps1' and WIN:   # on Linux the pwsh shim runs the shell twin, which needs a shell stub
        f = d / 'gh.cmd'
        f.write_text('@echo off\r\necho %* >>"%STUB_LOG%"\r\nif "%1"=="auth" goto auth\r\nif "%2"=="list" goto list\r\nif "%2"=="create" goto create\r\nexit /b 0\r\n'
                     ':auth\r\nif "%STUB_MODE%"=="noauth" exit /b 1\r\nexit /b 0\r\n:list\r\nif "%STUB_MODE%"=="dup" (echo [{"url":"https://github.com/test/repo/issues/9"}]) else (echo [])\r\nexit /b 0\r\n'
                     ':create\r\necho https://github.com/test/repo/issues/10\r\nexit /b 0\r\n', encoding='ascii')
    else:
        f = d / 'gh'
        f.write_text('#!/bin/sh\necho "$*" >> "$STUB_LOG"\ncase "$1 $2" in\n "auth status") [ "$STUB_MODE" = noauth ] && exit 1; exit 0 ;;\n'
                     ' "issue list") if [ "$STUB_MODE" = dup ]; then echo \'[{"url":"https://github.com/test/repo/issues/9"}]\'; else echo "[]"; fi; exit 0 ;;\n'
                     ' "issue create") echo "https://github.com/test/repo/issues/10"; exit 0 ;;\nesac\nexit 0\n', encoding='ascii', newline='\n')
        f.chmod(0o755)
    return f


def run(cmd, data, *args, mode='ok', gh=None, log=None):
    env = dict(os.environ, AGENT_KIT_DATA=str(data), AGENT_KIT_REPO='test/repo', STUB_MODE=mode, STUB_LOG=str(log or (TMP / 'stub.log')))
    env.pop('CLAUDE_CONFIG_DIR', None)
    if gh:
        env['AGENT_KIT_GH'] = str(gh)
    else:
        env['AGENT_KIT_GH'] = str(TMP / 'no-such-gh-program')   # never reach a real gh
    return subprocess.run(cmd + list(args), capture_output=True, text=True, timeout=180, env=env)


def stamp(minutes=0, days=0):
    t = NOW - datetime.timedelta(minutes=minutes, days=days)
    return t.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def fixture(tag):
    d = TMP / f'data-{tag}'
    (d / 'eval').mkdir(parents=True, exist_ok=True)
    s = chr(92)
    lines = [
        f'{stamp(5)} check-bulk-read: audit write failed: cannot append to C:{s}Users{s}jdoe{s}.claude{s}agent-kit{s}audit{s}x.jsonl',
        f'{stamp(4)} check-bulk-read: audit write failed: cannot append to C:{s}Users{s}jdoe{s}.claude{s}agent-kit{s}audit{s}x.jsonl',
        f'{stamp(3)} subagent-usage-log: run record not written: token=ghp_abcdefghijklmnop1234 mail a.b@corp.com /home/alice/proj/file.txt',
        f'{stamp(2)} guard-browser audit write failed (allow nav): Access to the path \'D:{s}work{s}project-x{s}audit{s}a.jsonl\' is denied after 12 tries',
        f'{stamp(1)} guard-browser audit write failed (allow nav): Access to the path \'D:{s}work{s}project-x{s}audit{s}a.jsonl\' is denied after 7 tries',
        f'{stamp(0)} inject-context: key 0123456789abcdef0123456789abcdef0123 leaked',
        f'{stamp(days=90)} old-script: this one is outside the window',
        'not a log line at all',
    ]
    (d / 'hook-errors.log').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def ann(ts, agent, outcome, code, sev, verified):
        return json.dumps({'schema': 'agent-annotation/1', 'ts': ts, 'agent_type': agent, 'outcome': outcome, 'code': code, 'severity': sev, 'verified': verified,
                           'summary': 'PRIVATE SUMMARY TEXT must never appear', 'claim': 'PRIVATE CLAIM'})
    (d / 'eval' / 'annotations.jsonl').write_text('\n'.join([
        ann(stamp(10), 'code-explorer', 'wrong', 'wrong_count', 'medium', 'yes'),
        ann(stamp(9), 'code-explorer', 'wrong', 'wrong_count', 'medium', 'yes'),
        ann(stamp(8), 'code-explorer', 'wrong', 'wrong_count', 'medium', 'no'),
        ann(stamp(7), 'Evil Agent! ghp_zzzzzzzzzzzzzzzzzzzz', 'partial', 'omission', 'low', 'yes'),
        ann(stamp(days=90), 'old-agent', 'wrong', 'other', 'low', 'yes'),
    ]) + '\n', encoding='utf-8')
    return d


def parse(out):
    r = {}
    for line in out.splitlines():
        m = re.match(r'^(DRAFT|TITLE|FINGERPRINT|CREATED|DUPLICATE|NO_GH|REJECTED|FAILED|NO ERRORS)\b ?(.*)$', line)
        if m:
            r[m.group(1)] = m.group(2)
    return r


def body_without_environment(text):
    return '\n'.join(x for x in text.replace('\r\n', '\n').split('\n') if not x.startswith('**Versions:**'))


def main():
    ts = tools()
    check('at least one issue-report tool can run here', bool(ts))
    drafts = {}
    for t, cmd in ts.items():
        d = fixture(t)
        p = run(cmd, d, 'draft')
        r = parse(p.stdout)
        check(f'[{t}] draft exits 0 and names the draft, title and fingerprint', p.returncode == 0 and r.get('DRAFT') and r.get('TITLE') and re.fullmatch(r'[0-9a-f]{12}', r.get('FINGERPRINT', '')), p.stdout + p.stderr)
        check(f'[{t}] draft says nothing was sent', 'NOTHING SENT' in p.stdout)
        if not r.get('DRAFT'):
            continue
        path = pathlib.Path(r['DRAFT'])
        if not path.exists() and WIN:
            path = pathlib.Path(r['DRAFT'].replace('/', os.sep))
        txt = path.read_text(encoding='utf-8') if path.exists() else ''
        drafts[t] = (txt, r)
        check(f'[{t}] draft file exists inside the reports folder', path.exists() and path.parent.name == 'reports' and path.name.startswith('issue-draft-'), str(path))
        low = txt.lower()
        for bad in ('jdoe', 'alice', 'ghp_abcdefghijklmnop1234', 'ghp_zzzz', 'corp.com', 'project-x', '0123456789abcdef0123456789abcdef', 'private summary', 'private claim', 'old-script', 'old-agent', 'evil agent'):
            check(f'[{t}] draft does not contain {bad!r}', bad not in low, bad)
        check(f'[{t}] the two identical bulk-read errors are one row with count 2', re.search(r'\| 2 \| \S+ \| \S+ \| `check-bulk-read` \|', txt) is not None, txt)
        check(f'[{t}] errors that differ only in digits are one row with count 2', re.search(r'\| 2 \| \S+ \| \S+ \| `guard-browser` \|.*12 tries|\| 2 \| \S+ \| \S+ \| `guard-browser` \|.*N tries|\| 2 \| \S+ \| \S+ \| `guard-browser` \|', txt) is not None, txt)
        check(f'[{t}] home and path text is replaced', '<home>' in txt and '<path>/' in txt, txt)
        check(f'[{t}] secrets and addresses are replaced', '<redacted:secret>' in txt and '<email>' in txt, txt)
        check(f'[{t}] annotation rows are counted: code-explorer 2, unverified-no left out, odd agent type becomes "other"', '| 2 | `code-explorer` | wrong | wrong_count | medium |' in txt and '| 1 | `other` | partial | omission | low |' in txt, txt)
        check(f'[{t}] the draft starts with the fingerprint line and a title line', txt.startswith('<!-- agent-kit-report fingerprint: ') and txt.split('\n')[1].startswith('<!-- title: '), txt[:200])
        check(f'[{t}] the draft says what it never contains', 'No prompts, answers, transcripts or file contents' in txt)
        # empty data folder
        e = TMP / f'empty-{t}'
        e.mkdir(exist_ok=True)
        p = run(cmd, e, 'draft')
        check(f'[{t}] no errors: says so, exits 0, writes no draft', p.returncode == 0 and 'NO ERRORS' in p.stdout and not (e / 'reports').exists(), p.stdout + p.stderr)
        # arguments
        p = run(cmd, d, 'draft', '-Days', '0')
        check(f'[{t}] -Days 0 is rejected', p.returncode == 2 and 'REJECTED' in p.stdout, p.stdout + p.stderr)
        p = run(cmd, d, 'bogus')
        check(f'[{t}] an unknown action is rejected', p.returncode == 2 and 'REJECTED' in p.stdout, p.stdout + p.stderr)
        p = run(cmd, d, 'draft', '-Days', '1')
        check(f'[{t}] a one-day window still finds today\'s errors', p.returncode == 0 and 'DRAFT' in p.stdout, p.stdout + p.stderr)

    if len(drafts) == 2:
        a, b = drafts['sh'], drafts['ps1']
        check('sh and ps1 print the same fingerprint', a[1]['FINGERPRINT'] == b[1]['FINGERPRINT'], f"{a[1]['FINGERPRINT']} vs {b[1]['FINGERPRINT']}")
        check('sh and ps1 print the same title', a[1]['TITLE'] == b[1]['TITLE'], f"{a[1]['TITLE']!r} vs {b[1]['TITLE']!r}")
        x, y = body_without_environment(a[0]), body_without_environment(b[0])
        check('sh and ps1 write the same draft (apart from the Versions line)', x == y, '\n--- sh\n' + x + '\n--- ps1\n' + y)

    # submit
    for t, cmd in ts.items():
        d = TMP / f'data-{t}'
        if not (d / 'reports').exists():
            continue
        stub = make_stub(t)
        draft = sorted((d / 'reports').glob('issue-draft-*.md'))[0]
        base = draft.read_text(encoding='utf-8')
        p = run(cmd, d, 'submit')
        check(f'[{t}] submit without -Draft is rejected', p.returncode == 2 and 'REJECTED' in p.stdout, p.stdout + p.stderr)
        outside = TMP / f'issue-draft-outside-{t}.md'
        outside.write_text(base, encoding='utf-8')
        p = run(cmd, d, 'submit', '-Draft', str(outside), gh=stub)
        check(f'[{t}] a draft outside the reports folder is rejected and gh is not called', p.returncode == 2 and 'REJECTED' in p.stdout and not (TMP / 'stub.log').exists(), p.stdout + p.stderr)
        wrong = d / 'reports' / 'notes.md'
        wrong.write_text(base, encoding='utf-8')
        p = run(cmd, d, 'submit', '-Draft', str(wrong), gh=stub)
        check(f'[{t}] a file not named issue-draft-*.md is rejected', p.returncode == 2 and 'REJECTED' in p.stdout, p.stdout + p.stderr)
        nofp = d / 'reports' / 'issue-draft-nofp.md'
        nofp.write_text(base.split('\n', 1)[1], encoding='utf-8')
        p = run(cmd, d, 'submit', '-Draft', str(nofp), gh=stub)
        check(f'[{t}] a draft without the fingerprint line is rejected', p.returncode == 2 and 'REJECTED' in p.stdout, p.stdout + p.stderr)

        # the user edits the draft and leaves a secret in it: submit sanitizes it again
        edited = d / 'reports' / 'issue-draft-edited.md'
        edited.write_text(base + '\nnote from the user: password=hunter2hunter2 on C:' + chr(92) + 'Users' + chr(92) + 'bob' + chr(92) + 'x\n', encoding='utf-8')
        log = TMP / f'stub-{t}.log'
        log.unlink(missing_ok=True)
        p = run(cmd, d, 'submit', '-Draft', str(edited), gh=stub, log=log)
        r = parse(p.stdout)
        calls = log.read_text(encoding='utf-8') if log.exists() else ''
        check(f'[{t}] submit with gh logged in creates the issue and prints its URL', p.returncode == 0 and r.get('CREATED') == 'https://github.com/test/repo/issues/10', p.stdout + p.stderr + calls)
        check(f'[{t}] gh is asked for an issue with the fingerprint first, then create, on the test repo', 'issue list' in calls and 'in:body' in calls and 'issue create --repo test/repo' in calls and calls.index('issue list') < calls.index('issue create'), calls)
        body = (d / 'reports' / '.submit-body.md').read_text(encoding='utf-8') if (d / 'reports' / '.submit-body.md').exists() else ''
        check(f'[{t}] the submitted body is sanitized again (user-added secret and user name are gone)', 'hunter2' not in body and 'bob' not in body and 'password=<redacted:secret>' in body, body[-300:])
        check(f'[{t}] the submitted body starts with the fingerprint and has no title comment', body.startswith('<!-- agent-kit-report fingerprint: ') and '<!-- title:' not in body, body[:200])
        check(f'[{t}] the issue title is passed to gh', '--title Error report: ' in calls.replace('"', ''), calls)

        log.unlink(missing_ok=True)
        p = run(cmd, d, 'submit', '-Draft', str(edited), mode='dup', gh=stub, log=log)
        r = parse(p.stdout)
        calls = log.read_text(encoding='utf-8') if log.exists() else ''
        check(f'[{t}] a known fingerprint prints DUPLICATE and creates nothing', p.returncode == 0 and r.get('DUPLICATE') == 'https://github.com/test/repo/issues/9' and 'issue create' not in calls, p.stdout + p.stderr + calls)

        p = run(cmd, d, 'submit', '-Draft', str(edited), mode='noauth', gh=stub, log=log)
        out = p.stdout
        check(f'[{t}] gh not logged in prints a prefilled browser link and creates nothing', p.returncode == 0 and 'NO_GH' in out and 'https://github.com/test/repo/issues/new?title=' in out and '&body=' in out, out + p.stderr)
        m = re.search(r'https://github\.com/test/repo/issues/new\?\S+', out)
        check(f'[{t}] the browser link is short enough to open (under 8000 characters)', bool(m) and len(m.group(0)) < 8000, str(len(m.group(0)) if m else 0))
        check(f'[{t}] the browser link carries no secret or user name', bool(m) and 'hunter2' not in m.group(0) and '%62%6f%62' not in m.group(0).lower(), '')

        p = run(cmd, d, 'submit', '-Draft', str(edited))
        check(f'[{t}] with no gh program at all it falls back to the browser link', p.returncode == 0 and 'NO_GH' in p.stdout, p.stdout + p.stderr)

    skill = (SCRIPTS.parent / 'skills' / 'report-issue' / 'SKILL.md').read_text(encoding='utf-8')
    check('SKILL.md is user-invoked only and starts the script through run.sh', 'disable-model-invocation: true' in skill and 'scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/issue-report' in skill)
    check('SKILL.md has no shell-language names and never allows a bare gh call', 'powershell' not in skill.lower() and '.ps1' not in skill and 'allowed-tools: Bash(sh ' in skill and 'Bash(gh' not in skill)
    check('SKILL.md asks the user before submit and says nothing is sent before', 'until the user has read the draft' in skill and 'Ask: ' in skill and 'never submit without the user' in skill)
    check('both twins of issue-report exist', (SCRIPTS / 'issue-report.sh').exists() and (SCRIPTS / 'issue-report.ps1').exists())
    print(f'{sum(results)}/{len(results)} passed')
    shutil.rmtree(TMP, ignore_errors=True) if TMP.name.startswith('issuereport_') and TMP.parent == pathlib.Path(tempfile.gettempdir()) else None
    sys.exit(0 if all(results) else 1)


main()
