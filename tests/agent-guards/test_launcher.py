"""Every hook and skill must start through the OS-neutral run.sh (PowerShell on Windows, POSIX sh on Linux; no extension in any command). Run: python test_launcher.py"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALL_PLUGINS = sorted(p for p in (ROOT / 'plugins').iterdir() if p.is_dir())
# a plugin with agents and prompt-only skills (no scripts or hooks folder, for example code-review) has nothing to launch and needs no run.sh or lib.sh
PLUGINS = [p for p in ALL_PLUGINS if (p / 'scripts').is_dir() or (p / 'hooks').is_dir()]
SH = shutil.which('sh')
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    check('sh is available to run the launcher', SH, 'no sh on PATH')
    for p in PLUGINS:
        launcher = p / 'scripts' / 'run.sh'
        check(f'{p.name}: run.sh exists', launcher.is_file())
        if launcher.is_file():
            raw = launcher.read_bytes()
            check(f'{p.name}: run.sh uses LF line endings', b'\r' not in raw)
        hooks = p / 'hooks' / 'hooks.json'
        if not hooks.is_file():
            continue
        data = json.loads(hooks.read_text(encoding='utf-8'))
        cmds = [h['command'] for evt in data['hooks'].values() for grp in evt for h in grp['hooks']]
        check(f'{p.name}: hooks go through run.sh', cmds and all('scripts/run.sh' in c and 'powershell.exe' not in c for c in cmds), str(cmds))
        check(f'{p.name}: hooks read their input with a time limit (run.sh --hook)', all('scripts/run.sh\\" --hook ' in c or 'scripts/run.sh" --hook ' in c for c in cmds), str(cmds))
        # a hook that fails or times out decided nothing; only a guard whose every call is in scope may block on that
        blocking = [h['command'] for evt in data['hooks'].values() for grp in evt for h in grp['hooks'] if h.get('onFailure') == 'block']
        check(f'{p.name}: only guard-browser blocks when the hook fails', all('scripts/guard-browser' in c for c in blocking), str(blocking))
        # every script a hook names (no extension) must exist as a PowerShell and as a shell version, and lib.sh must be identical everywhere
        for c in cmds:
            m = re.findall(r'scripts/([A-Za-z0-9_-]+)(?:\\"|"|$)', c.replace('\\"', '"'))
            name = m[-1] if m else ''
            check(f'{p.name}: hook script {name} has .ps1 and .sh', name and name != 'run' and (p / 'scripts' / (name + '.ps1')).is_file() and (p / 'scripts' / (name + '.sh')).is_file(), c)
            check(f'{p.name}: hook command for {name} has no shell-language extension', '.ps1' not in c and '.sh"' not in c.replace('run.sh', ''), c)
    for skill in sorted((ROOT / 'plugins').glob('*/skills/*/SKILL.md')):
        t = skill.read_text(encoding='utf-8')
        # a shell script must start through run.sh; a Node script (.mjs) is the same on every OS and needs no launcher
        runs_scripts = any('scripts/' in line and '.mjs' not in line for line in t.splitlines())
        check(f'{skill.parent.name}: skill commands go through run.sh', 'powershell' not in t.lower() and '.ps1' not in t and ('scripts/run.sh' in t or not runs_scripts))

    libs = {p.name: (p / 'scripts' / 'lib.sh').read_bytes() for p in PLUGINS if (p / 'scripts' / 'lib.sh').is_file()}
    check('lib.sh is identical in every plugin that ships scripts', len(libs) == len(PLUGINS) and len(set(libs.values())) == 1, str(sorted(libs)))
    routers = {p.name: (p / 'scripts' / 'run.sh').read_bytes() for p in PLUGINS if (p / 'scripts' / 'run.sh').is_file()}
    check('run.sh is identical in every plugin that ships scripts', len(routers) == len(PLUGINS) and len(set(routers.values())) == 1, str(sorted(routers)))
    check('every plugin without scripts or hooks is documentation only (agents or skills)', all((p / 'agents').is_dir() or (p / 'skills').is_dir() for p in ALL_PLUGINS if p not in PLUGINS), str([p.name for p in ALL_PLUGINS if p not in PLUGINS]))
    check('lib.sh uses LF line endings', all(b'\r' not in v for v in libs.values()))

    if not SH:
        return
    guards = ROOT / 'plugins' / 'haiku-delegation' / 'scripts'
    # the launcher runs a script, passes stdin and arguments through, and returns its exit code
    with tempfile.TemporaryDirectory() as td:
        ps_src = 'param([string]$A)\n$in = [Console]::In.ReadToEnd()\nWrite-Output ("A=" + $A + " IN=" + $in.Trim())\nexit 7\n'
        sh_src = 'while [ $# -gt 0 ]; do case "$1" in -A) a="$2"; shift 2;; *) shift;; esac; done\nin=$(cat)\nprintf "A=%s IN=%s\\n" "$a" "$in"\nexit 7\n'
        (pathlib.Path(td) / 'echo.ps1').write_text(ps_src, encoding='utf-8')
        (pathlib.Path(td) / 'echo.sh').write_text(sh_src, encoding='utf-8', newline='\n')
        ps1 = pathlib.Path(td) / 'echo'
        p = subprocess.run([SH, str(guards / 'run.sh'), str(ps1), '-A', 'hello'], input='piped', capture_output=True, text=True, timeout=120)
        check('launcher passes args and stdin through', 'A=hello IN=piped' in p.stdout, p.stdout + p.stderr)
        check('launcher returns the script exit code', p.returncode == 7, str(p.returncode))
        p = subprocess.run([SH, str(guards / 'run.sh'), '--hook', str(ps1), '-A', 'hello'], input='{"k":1}', capture_output=True, text=True, timeout=120)
        check('launcher --hook passes args, stdin and the exit code through', 'A=hello IN={"k":1}' in p.stdout and p.returncode == 7, p.stdout + p.stderr)
        # a script with no shell version: clear message, exit 2 (a guard that cannot run blocks instead of being skipped)
        p = subprocess.run([SH, str(guards / 'run.sh'), str(pathlib.Path(td) / 'nothere')], capture_output=True, text=True, timeout=60)
        check('missing script version: exit 2', p.returncode == 2, str(p.returncode))
        p = subprocess.run([SH, str(guards / 'run.sh')], capture_output=True, text=True, timeout=60)
        check('no script argument: exit 2', p.returncode == 2, str(p.returncode))
    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
