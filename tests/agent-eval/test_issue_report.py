"""/agent-eval:report-issue (issue-report.sh and issue-report.ps1): the draft holds only sanitized, aggregated evidence, both tools write the same draft,
nothing is sent without `submit`, and `submit` is limited to drafts in the reports folder. gh is always a stub (AGENT_KIT_GH); no test talks to GitHub.
The recorded cases (cases/issue-report.json: the draft, the rejections and the submit flows through a gh stub) are replayed through each implementation
that runs here (see tests/golden.py); the Versions line is masked there and checked below. The checks that depend on today's date (a one-day window) and the
Versions line are run here on a fresh fixture. Run: python test_issue_report.py   (temp data folders only)"""
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import capability_variants, summary  # noqa: E402
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'agent-eval' / 'scripts'
CASES = Path(__file__).resolve().parent / 'cases'
TMP = pathlib.Path(tempfile.mkdtemp(prefix='issuereport_'))
results = []
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def run(cmd, data, *args):
    env = dict(os.environ, AGENT_KIT_DATA=str(data), AGENT_KIT_REPO='test/repo', AGENT_KIT_GH=str(TMP / 'no-such-gh-program'))
    env.pop('CLAUDE_CONFIG_DIR', None)
    return subprocess.run(cmd + list(args), capture_output=True, text=True, timeout=180, env=env)


def stamp(minutes=0, days=0):
    t = NOW - datetime.timedelta(minutes=minutes, days=days)
    return t.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def fresh_fixture(tag):
    """errors and annotations stamped relative to today: the one-day window must find them"""
    d = TMP / f'data-{tag}'
    (d / 'eval').mkdir(parents=True, exist_ok=True)
    bs = chr(92)
    lines = [
        f'{stamp(5)} check-bulk-read: audit write failed: cannot append to C:{bs}Users{bs}jdoe{bs}.claude{bs}agent-kit{bs}audit{bs}x.jsonl',
        f'{stamp(4)} check-bulk-read: audit write failed: cannot append to C:{bs}Users{bs}jdoe{bs}.claude{bs}agent-kit{bs}audit{bs}x.jsonl',
        f'{stamp(3)} subagent-usage-log: run record not written: token=ghp_abcdefghijklmnop1234 mail a.b@corp.com /home/alice/proj/file.txt',
        f'{stamp(0)} inject-context: key 0123456789abcdef0123456789abcdef0123 leaked',
    ]
    (d / 'hook-errors.log').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    row = json.dumps({'schema': 'agent-annotation/1', 'ts': stamp(10), 'agent_type': 'code-explorer', 'outcome': 'wrong', 'code': 'wrong_count',
                      'severity': 'medium', 'verified': 'yes', 'summary': 'PRIVATE SUMMARY TEXT must never appear', 'claim': 'PRIVATE CLAIM'})
    (d / 'eval' / 'annotations.jsonl').write_text(row + '\n', encoding='utf-8')
    return d


def main():
    ts = capability_variants(SCRIPTS / 'issue-report')
    check('at least one issue-report tool can run here', bool(ts))

    # the recorded behaviour, through each implementation
    golden.replay(CASES / 'issue-report.json', SCRIPTS / 'issue-report', results, check)

    plugin_json = json.loads((SCRIPTS.parent / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
    for t, cmd in ts.items():
        d = fresh_fixture(t)
        p = run(cmd, d, 'draft', '-Days', '1')
        m = re.search(r'^DRAFT (.+)$', p.stdout, re.M)
        check(f'[{t}] a one-day window still finds today\'s errors', p.returncode == 0 and m is not None, p.stdout + p.stderr)
        if not m:
            continue
        path = pathlib.Path(m.group(1).strip())
        if not path.exists():
            path = pathlib.Path(m.group(1).strip().replace('/', os.sep))
        txt = path.read_text(encoding='utf-8') if path.exists() else ''
        check(f'[{t}] the draft is inside the reports folder', path.exists() and path.parent.name == 'reports' and path.name.startswith('issue-draft-'), str(path))
        check(f'[{t}] the two identical bulk-read errors are one row with count 2', re.search(r'\| 2 \| \S+ \| \S+ \| `check-bulk-read` \|', txt) is not None, txt)
        check(f'[{t}] home and path text is replaced, secrets and addresses are replaced', '<home>' in txt and '<path>/' in txt and '<redacted:secret>' in txt and '<email>' in txt, txt)
        vm = re.search(r'^\*\*Versions:\*\* agent-kit (\d+\.\d+\.\d+) \(agent-eval (\d+\.\d+\.\d+), agent-guards (\d+\.\d+\.\d+), haiku-delegation (\d+\.\d+\.\d+), verification-runner (\d+\.\d+\.\d+)\), claude-code (\S+), os (.+)$', txt, re.M)
        check(f'[{t}] the Versions line names the kit, all four plugins, Claude Code and the OS', vm is not None, txt[:600])
        check(f'[{t}] the kit and plugin versions are the ones in plugin.json', vm is not None and set(vm.groups()[:5]) == {plugin_json['version']}, str(vm.groups() if vm else ''))
        check(f'[{t}] the title starts with the kit version', f"[agent-kit {plugin_json['version']}] " in p.stdout, p.stdout[:300])
        check(f'[{t}] the draft says what it never contains', 'No prompts, answers, transcripts or file contents' in txt)
        e = TMP / f'empty-{t}'
        e.mkdir(exist_ok=True)
        p = run(cmd, e, 'draft')
        check(f'[{t}] no errors: says so, exits 0, writes no draft', p.returncode == 0 and 'NO ERRORS' in p.stdout and not (e / 'reports').exists(), p.stdout + p.stderr)

    skill = (SCRIPTS.parent / 'skills' / 'report-issue' / 'SKILL.md').read_text(encoding='utf-8')
    check('SKILL.md is user-invoked only and starts the script through run.sh', 'disable-model-invocation: true' in skill and 'scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/issue-report' in skill)
    check('SKILL.md has no shell-language names and never allows a bare gh call', 'powershell' not in skill.lower() and '.ps1' not in skill and 'allowed-tools: Bash(sh ' in skill and 'Bash(gh' not in skill)
    check('SKILL.md asks the user before submit and says nothing is sent before', 'until the user has read the draft' in skill and 'Ask: ' in skill and 'never submit without the user' in skill)
    check('both twins of issue-report exist', (SCRIPTS / 'issue-report.sh').exists() and (SCRIPTS / 'issue-report.ps1').exists())
    print(summary(results))
    shutil.rmtree(TMP, ignore_errors=True) if TMP.name.startswith('issuereport_') and TMP.parent == pathlib.Path(tempfile.gettempdir()) else None
    sys.exit(0 if all(results) else 1)


main()
