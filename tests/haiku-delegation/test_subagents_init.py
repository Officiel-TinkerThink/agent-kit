"""/subagents-init: copies SUBAGENTS.md to a project and imports it from CLAUDE.md or AGENTS.md without overwriting anything.
Runs the same scenarios against the POSIX sh tool and the PowerShell tool (whichever exist here) and requires identical stdout.
Run: python test_subagents_init.py"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'plugins' / 'haiku-delegation'
SCRIPTS = PLUGIN / 'scripts'
TEMPLATE = PLUGIN / 'templates' / 'SUBAGENTS.md'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def runners():
    out = {}
    if shutil.which('sh'):
        out['sh'] = lambda args: ['sh', str(SCRIPTS / 'subagents-init.sh')] + args
    ps = shutil.which('powershell.exe') or shutil.which('powershell')
    if ps:
        out['ps1'] = lambda args: [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / 'subagents-init.ps1')] + args
    return out


def run(make, project, *args):
    p = subprocess.run(make(['-Project', str(project)] + list(args)), capture_output=True, text=True, timeout=120)
    # the ROOT line differs by path spelling between the two tools; the rest must match exactly
    lines = [l for l in p.stdout.splitlines() if not l.startswith('ROOT:')]
    return p.returncode, lines, p.stderr


def read(p):
    return pathlib.Path(p).read_bytes()


def main():
    shipped = (ROOT / 'SUBAGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    tmpl = TEMPLATE.read_bytes().replace(b'\r\n', b'\n')
    check('shipped template equals the repo SUBAGENTS.md (copy it again after editing the root file)', shipped == tmpl)
    check('template has a Project facts section and the annotator duty', b'\n## Project facts' in tmpl and b'Report agent failures to the annotator' in tmpl)
    skill = (PLUGIN / 'skills' / 'subagents-init' / 'SKILL.md').read_text(encoding='utf-8')
    check('skill is user-only and goes through run.sh', 'disable-model-invocation: true' in skill and 'scripts/run.sh' in skill and 'subagents-init' in skill)

    tools = runners()
    check('at least one tool can run here', bool(tools))
    transcripts = {}
    for name, make in tools.items():
        with tempfile.TemporaryDirectory() as td:
            proj = pathlib.Path(td) / 'p'
            proj.mkdir()
            log = []

            def step(label, *args):
                rc, lines, err = run(make, proj, *args)
                log.append((label, rc, lines))
                return rc, lines, err

            # empty project: creates both files
            rc, lines, err = step('fresh')
            check(f'[{name}] fresh project: exit 0', rc == 0, err)
            check(f'[{name}] fresh project: SUBAGENTS.md is the template, byte for byte', (proj / 'SUBAGENTS.md').is_file() and read(proj / 'SUBAGENTS.md') == TEMPLATE.read_bytes())
            check(f'[{name}] fresh project: CLAUDE.md created with one import', (proj / 'CLAUDE.md').read_text(encoding='utf-8').count('@SUBAGENTS.md') == 1)
            check(f'[{name}] fresh project: stdout names what happened', 'CREATED SUBAGENTS.md' in lines and 'IMPORT created CLAUDE.md' in lines and lines[-1] == 'DONE', str(lines))

            # second run changes nothing
            before = (read(proj / 'SUBAGENTS.md'), read(proj / 'CLAUDE.md'))
            rc, lines, err = step('again')
            check(f'[{name}] second run: no change and no duplicate import', rc == 0 and before == (read(proj / 'SUBAGENTS.md'), read(proj / 'CLAUDE.md')) and 'IMPORT already in CLAUDE.md' in lines, str(lines))

            # a project's own SUBAGENTS.md is kept without -Update
            own = b'# My roster\n\nmine\n\n## Project facts\n\n- layout: src/\n'
            (proj / 'SUBAGENTS.md').write_bytes(own)
            rc, lines, err = step('exists')
            check(f'[{name}] differing SUBAGENTS.md is kept without -Update', rc == 0 and read(proj / 'SUBAGENTS.md') == own and any(l.startswith('EXISTS') for l in lines), str(lines))

            # -DryRun writes nothing
            rc, lines, err = step('dry', '-Update', '-DryRun')
            check(f'[{name}] -DryRun writes nothing', rc == 0 and read(proj / 'SUBAGENTS.md') == own and not list(proj.glob('SUBAGENTS.md.bak-*')) and 'WOULD UPDATE SUBAGENTS.md (backup first)' in lines, str(lines))

            # -Update refreshes the shipped part, keeps the project's facts, writes one backup
            rc, lines, err = step('update', '-Update')
            new = read(proj / 'SUBAGENTS.md')
            baks = list(proj.glob('SUBAGENTS.md.bak-*'))
            check(f'[{name}] -Update keeps the project facts and takes the shipped text above them', rc == 0 and new.endswith(b'## Project facts\n\n- layout: src/\n') and new.split(b'## Project facts')[0].replace(b'\r\n', b'\n') == tmpl.split(b'## Project facts')[0], str(lines))
            check(f'[{name}] -Update wrote exactly one backup of the previous file', len(baks) == 1 and baks[0].read_bytes() == own, str(baks))
            log[-1] = (log[-1][0], log[-1][1], [re.sub(r'bak-\d{8}T\d{6}Z', 'bak-STAMP', l) for l in log[-1][2]])

            # -Update twice is idempotent: same bytes, no second backup, UNCHANGED reported, import not duplicated
            after_first = (read(proj / 'SUBAGENTS.md'), read(proj / 'CLAUDE.md'))
            rc, lines, err = step('update-again', '-Update')
            check(f'[{name}] -Update twice: nothing changes and no second backup', rc == 0 and after_first == (read(proj / 'SUBAGENTS.md'), read(proj / 'CLAUDE.md')) and len(list(proj.glob('SUBAGENTS.md.bak-*'))) == 1 and 'UNCHANGED SUBAGENTS.md (shipped part already up to date)' in lines, str(lines))

            # -Update on a file without the marker is refused, nothing changes
            (proj / 'SUBAGENTS.md').write_bytes(b'# no marker\n')
            rc, lines, err = step('nomarker', '-Update')
            check(f'[{name}] -Update without a Project facts section is refused', rc == 1 and 'REFUSED' in err and read(proj / 'SUBAGENTS.md') == b'# no marker\n', err)

        # AGENTS.md only: import goes there, text above it stays byte for byte, a missing final newline is handled
        with tempfile.TemporaryDirectory() as td:
            proj = pathlib.Path(td) / 'p'
            proj.mkdir()
            original = b'# Agents\n\nuse tabs\n\xc3\xa9 no final newline'
            (proj / 'AGENTS.md').write_bytes(original)
            rc, lines, err = step_run = run(make, proj)
            body = read(proj / 'AGENTS.md')
            check(f'[{name}] AGENTS.md only: import added there, CLAUDE.md not created', rc == 0 and not (proj / 'CLAUDE.md').exists() and body.startswith(original) and body.endswith(b'@SUBAGENTS.md\n') and body.count(b'@SUBAGENTS.md') == 1, repr(body))
            log.append(('agents-only', rc, lines))
            # both files: CLAUDE.md wins, -Import agents overrides
            (proj / 'CLAUDE.md').write_bytes(b'# C\n')
            rc, lines, err = run(make, proj, '-Import', 'none')
            check(f'[{name}] -Import none leaves CLAUDE.md alone', rc == 0 and read(proj / 'CLAUDE.md') == b'# C\n', str(lines))
            rc, lines, err = run(make, proj)
            check(f'[{name}] both files: CLAUDE.md is the target', 'IMPORT added to CLAUDE.md' in lines and b'@SUBAGENTS.md' in read(proj / 'CLAUDE.md'), str(lines))
            log.append(('both', rc, lines))

        # bad input
        rc, lines, err = run(make, pathlib.Path(tempfile.gettempdir()) / 'does-not-exist-subagents-init')
        check(f'[{name}] a missing -Project folder is refused', rc == 1 and 'REFUSED' in err, err)
        p = subprocess.run(make(['-Import', 'bogus']), capture_output=True, text=True, timeout=120)
        check(f'[{name}] a bad -Import value exits 1', p.returncode == 1, p.stderr)
        transcripts[name] = log

    if len(transcripts) == 2:
        check('sh and ps1 print identical lines for every scenario', transcripts['sh'] == transcripts['ps1'], f"{transcripts['sh']}\n{transcripts['ps1']}")


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
