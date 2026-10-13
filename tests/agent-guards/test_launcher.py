"""Every hook and skill must start PowerShell through run-ps.sh (works on Windows and Ubuntu). Run: python test_launcher.py"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGINS = sorted(p for p in (ROOT / 'plugins').iterdir() if p.is_dir())
SH = shutil.which('sh')
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    check('sh is available to run the launcher', SH, 'no sh on PATH')
    for p in PLUGINS:
        launcher = p / 'scripts' / 'run-ps.sh'
        check(f'{p.name}: run-ps.sh exists', launcher.is_file())
        if launcher.is_file():
            raw = launcher.read_bytes()
            check(f'{p.name}: run-ps.sh uses LF line endings', b'\r' not in raw)
        hooks = p / 'hooks' / 'hooks.json'
        if not hooks.is_file():
            continue
        data = json.loads(hooks.read_text(encoding='utf-8'))
        cmds = [h['command'] for evt in data['hooks'].values() for grp in evt for h in grp['hooks']]
        check(f'{p.name}: hooks go through run-ps.sh', cmds and all('scripts/run-ps.sh' in c and 'powershell.exe' not in c for c in cmds), str(cmds))
        # every script a hook names must exist next to the launcher
        for c in cmds:
            m = re.findall(r'scripts/([A-Za-z0-9_.-]+\.ps1)', c)
            check(f'{p.name}: hook script exists {m}', m and (p / 'scripts' / m[-1]).is_file(), c)
    for skill in sorted((ROOT / 'plugins').glob('*/skills/*/SKILL.md')):
        t = skill.read_text(encoding='utf-8')
        check(f'{skill.parent.name}: skill commands go through run-ps.sh', 'powershell.exe' not in t and 'scripts/run-ps.sh' in t)

    if not SH:
        return
    guards = ROOT / 'plugins' / 'haiku-delegation' / 'scripts'
    # the launcher runs a script, passes stdin and arguments through, and returns its exit code
    with tempfile.TemporaryDirectory() as td:
        ps1 = pathlib.Path(td) / 'echo.ps1'
        ps1.write_text('param([string]$A)\n$in = [Console]::In.ReadToEnd()\nWrite-Output ("A=" + $A + " IN=" + $in.Trim())\nexit 7\n', encoding='utf-8')
        p = subprocess.run([SH, str(guards / 'run-ps.sh'), str(ps1), '-A', 'hello'], input='piped', capture_output=True, text=True, timeout=120)
        check('launcher passes args and stdin through', 'A=hello IN=piped' in p.stdout, p.stdout + p.stderr)
        check('launcher returns the script exit code', p.returncode == 7, str(p.returncode))
        # no PowerShell on PATH: clear message, exit 2 (blocks a guard rather than silently skipping it)
        empty = pathlib.Path(td) / 'empty'
        empty.mkdir()
        p = subprocess.run([SH, str(guards / 'run-ps.sh'), str(ps1)], capture_output=True, text=True, timeout=60, env=dict(os.environ, PATH=str(empty)))
        check('missing PowerShell: exit 2', p.returncode == 2, str(p.returncode))
        check('missing PowerShell: says how to install pwsh', 'PowerShell 7' in p.stderr and 'pwsh' in p.stderr, p.stderr)
        p = subprocess.run([SH, str(guards / 'run-ps.sh')], capture_output=True, text=True, timeout=60)
        check('no script argument: exit 2', p.returncode == 2, str(p.returncode))
    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
