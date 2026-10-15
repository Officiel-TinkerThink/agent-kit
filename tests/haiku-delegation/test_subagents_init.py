"""/subagents-init: copies SUBAGENTS.md to a project, imports it from CLAUDE.md or AGENTS.md and adds the shipped AGENTS.md text there as a marked block, without overwriting anything.
Runs the same scenarios against the POSIX sh tool and the PowerShell tool (whichever exist here) and requires identical stdout.
Run: python test_subagents_init.py"""
import concurrent.futures
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
BEGIN = b'<!-- agent-kit:orchestration:begin'
END = b'<!-- agent-kit:orchestration:end -->'


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def runners():
    out = {}
    if shutil.which('sh'):
        out['sh'] = lambda args: ['sh', str(SCRIPTS / 'subagents-init.sh')] + args
    ps = (shutil.which('powershell.exe') or shutil.which('powershell')) if sys.platform == 'win32' else shutil.which('pwsh')   # not the Windows powershell.exe that WSL exposes through interop: it cannot open Linux paths
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


def agents_text():
    """the shipped orchestration text as the tools write it: LF only, one final newline"""
    t = (PLUGIN / 'templates' / 'AGENTS.md').read_bytes().replace(b'\r', b'')
    return t if t.endswith(b'\n') else t + b'\n'


def inner(body):
    """the text between the two marker lines (LF only)"""
    b = body.replace(b'\r', b'')
    i, j = b.index(BEGIN), b.index(END)
    return b[b.index(b'\n', i) + 1:j]


def stamp(lines):
    return [re.sub(r'bak-\d{8}T\d{6}Z', 'bak-STAMP', l) for l in lines]


def orchestration(name, make, log):
    tpl = agents_text()
    own = b'# My project\n\nOwn rules.\n- keep me exactly'   # no final newline
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / 'p'
        proj.mkdir()
        (proj / 'CLAUDE.md').write_bytes(own)
        rc, lines, err = run(make, proj)
        log.append(('orch-add', rc, lines))
        body = read(proj / 'CLAUDE.md')
        check(f'[{name}] orchestration: added to CLAUDE.md and the project\'s own text is kept byte for byte', rc == 0 and 'ORCHESTRATION added to CLAUDE.md' in lines and body.startswith(own), str(lines) + repr(body[:120]))
        check(f'[{name}] orchestration: one begin and one end marker with the shipped text verbatim between them', body.count(BEGIN) == 1 and body.count(END) == 1 and inner(body) == tpl, repr(body[-200:]))
        check(f'[{name}] orchestration: the SUBAGENTS.md import is there once', body.count(b'@SUBAGENTS.md') == 1)
        before = body
        rc, lines, err = run(make, proj)
        log.append(('orch-again', rc, lines))
        check(f'[{name}] orchestration: second run changes nothing', rc == 0 and read(proj / 'CLAUDE.md') == before and 'ORCHESTRATION up to date in CLAUDE.md' in lines, str(lines))
        # the shipped text moved on: an old block with the user's own text after it
        tail = b'\nMy notes after the block.\n'
        mine = before.replace(b'Decompose before executing.', b'Decompose first.') + tail
        (proj / 'CLAUDE.md').write_bytes(mine)
        rc, lines, err = run(make, proj, '-Keep')
        log.append(('orch-outdated', rc, lines))
        check(f'[{name}] orchestration: with -Keep an outdated block is reported and left alone', rc == 0 and read(proj / 'CLAUDE.md') == mine and any(l.startswith('ORCHESTRATION outdated in CLAUDE.md; kept as it is (-Keep)') for l in lines), str(lines))
        rc, lines, err = run(make, proj, '-Update', '-DryRun')
        log.append(('orch-dry-update', rc, lines))
        check(f'[{name}] orchestration: -Update -DryRun writes nothing', rc == 0 and read(proj / 'CLAUDE.md') == mine and not list(proj.glob('CLAUDE.md.bak-*')) and 'WOULD UPDATE orchestration in CLAUDE.md (backup first)' in lines, str(lines))
        rc, lines, err = run(make, proj, '-Update')
        log.append(('orch-update', rc, stamp(lines)))
        new = read(proj / 'CLAUDE.md')
        baks = list(proj.glob('CLAUDE.md.bak-*'))
        check(f'[{name}] orchestration: -Update restores the shipped text and keeps everything before and after the block', rc == 0 and inner(new) == tpl and new.startswith(mine[:mine.index(BEGIN)]) and new.endswith(tail), str(lines) + repr(new[-120:]))
        check(f'[{name}] orchestration: -Update wrote one backup of the previous file', len(baks) == 1 and baks[0].read_bytes() == mine and any(l.startswith('ORCHESTRATION updated in CLAUDE.md (previous version: CLAUDE.md.bak-') for l in lines), str(baks) + str(lines))
        # refreshing is the default: the same outdated block, run with no flags
        (proj / 'CLAUDE.md').write_bytes(mine)
        for b in baks:
            b.unlink()
        rc, lines, err = run(make, proj)
        log.append(('orch-default-refresh', rc, stamp(lines)))
        new = read(proj / 'CLAUDE.md')
        baks = list(proj.glob('CLAUDE.md.bak-*'))
        check(f'[{name}] orchestration: with no flags an outdated block is refreshed, text around it kept, one backup written', rc == 0 and inner(new) == tpl and new.endswith(tail) and len(baks) == 1 and baks[0].read_bytes() == mine and any(l.startswith('ORCHESTRATION updated in CLAUDE.md (previous version: CLAUDE.md.bak-') for l in lines), str(lines))
    # the shipped text is already in the file, no markers: nothing is duplicated
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / 'p'
        proj.mkdir()
        (proj / 'CLAUDE.md').write_bytes(b'# P\n\n' + tpl + b'\nafter\n')
        rc, lines, err = run(make, proj)
        log.append(('orch-verbatim', rc, lines))
        body = read(proj / 'CLAUDE.md')
        check(f'[{name}] orchestration: text already in the file verbatim is not added again and gets no markers', rc == 0 and 'ORCHESTRATION already present in CLAUDE.md (verbatim; no markers added)' in lines and BEGIN not in body and body.count(tpl) == 1, str(lines))
    # a CRLF file gets a CRLF block
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / 'p'
        proj.mkdir()
        own = b'# C\r\n\r\nrules\r\n'
        (proj / 'CLAUDE.md').write_bytes(own)
        rc, lines, err = run(make, proj)
        log.append(('orch-crlf', rc, lines))
        body = read(proj / 'CLAUDE.md')
        seg = body[body.index(BEGIN):body.index(END) + len(END) + 2]
        check(f'[{name}] orchestration: a CRLF file keeps its text and gets the block with CRLF line ends', rc == 0 and body.startswith(own) and seg.count(b'\n') > 10 and seg.count(b'\n') == seg.count(b'\r\n') and inner(body) == tpl, str(lines))
        rc, lines, err = run(make, proj)
        log.append(('orch-crlf-again', rc, lines))
        check(f'[{name}] orchestration: a CRLF file is "up to date" on the second run', rc == 0 and 'ORCHESTRATION up to date in CLAUDE.md' in lines and read(proj / 'CLAUDE.md') == body, str(lines))
    # damaged markers are refused and nothing is written to the file
    for label, text in (('a begin marker without an end', b'# X\n\n@SUBAGENTS.md\n' + BEGIN + b' -->\nhalf a block\n'),
                        ('the end marker before the begin marker', b'# X\n\n@SUBAGENTS.md\n' + END + b'\n' + BEGIN + b' -->\n'),
                        ('a begin marker without an end (no import line yet)', b'# X\n' + BEGIN + b' -->\nhalf a block\n'),
                        ('two blocks', b'# X\n\n@SUBAGENTS.md\n' + BEGIN + b' -->\na\n' + END + b'\n' + BEGIN + b' -->\nb\n' + END + b'\n')):
        with tempfile.TemporaryDirectory() as td:
            proj = pathlib.Path(td) / 'p'
            proj.mkdir()
            (proj / 'CLAUDE.md').write_bytes(text)
            rc, lines, err = run(make, proj)
            check(f'[{name}] orchestration: {label} is refused and CLAUDE.md is not touched', rc == 1 and 'REFUSED' in err and 'markers' in err and read(proj / 'CLAUDE.md') == text, err)
    # switches
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / 'p'
        proj.mkdir()
        rc, lines, err = run(make, proj, '-NoOrchestration')
        log.append(('orch-off', rc, lines))
        check(f'[{name}] orchestration: -NoOrchestration adds the import but no block', rc == 0 and 'ORCHESTRATION skipped (-NoOrchestration)' in lines and BEGIN not in read(proj / 'CLAUDE.md'), str(lines))
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / 'p'
        proj.mkdir()
        (proj / 'CLAUDE.md').write_bytes(b'# C\n')
        rc, lines, err = run(make, proj, '-Import', 'none')
        log.append(('orch-import-none', rc, lines))
        check(f'[{name}] orchestration: -Import none adds neither import nor block', rc == 0 and 'ORCHESTRATION skipped (-Import none)' in lines and read(proj / 'CLAUDE.md') == b'# C\n', str(lines))
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / 'p'
        proj.mkdir()
        rc, lines, err = run(make, proj, '-DryRun')
        log.append(('orch-dry-fresh', rc, lines))
        check(f'[{name}] orchestration: -DryRun on an empty project says what it would do and writes nothing', rc == 0 and lines == ['WOULD CREATE SUBAGENTS.md', 'WOULD CREATE CLAUDE.md with the import', 'WOULD ADD orchestration to CLAUDE.md', 'DONE'] and not list(proj.iterdir()), str(lines))
    # AGENTS.md as the target: same block there
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / 'p'
        proj.mkdir()
        (proj / 'AGENTS.md').write_bytes(b'# Agents\n')
        rc, lines, err = run(make, proj)
        log.append(('orch-agents-target', rc, lines))
        check(f'[{name}] orchestration: goes into AGENTS.md when that is the import target', rc == 0 and 'ORCHESTRATION added to AGENTS.md' in lines and inner(read(proj / 'AGENTS.md')) == tpl and not (proj / 'CLAUDE.md').exists(), str(lines))


def main():
    shipped = (ROOT / 'SUBAGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    tmpl = TEMPLATE.read_bytes().replace(b'\r\n', b'\n')
    check('shipped template equals the repo SUBAGENTS.md (copy it again after editing the root file)', shipped == tmpl)
    check('template has a Project facts section and the annotator duty', b'\n## Project facts' in tmpl and b'Report agent failures to the annotator' in tmpl)
    ag_root = (ROOT / 'AGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    ag_tmpl = (PLUGIN / 'templates' / 'AGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    check('shipped AGENTS.md template equals the repo AGENTS.md (copy it again after editing the root file)', ag_root == ag_tmpl)
    check('AGENTS.md template is the orchestrator text and holds no marker text', ag_tmpl.startswith(b'# Orchestrator-First Execution') and b'agent-kit:orchestration' not in ag_tmpl)
    skill = (PLUGIN / 'skills' / 'subagents-init' / 'SKILL.md').read_text(encoding='utf-8')
    check('skill is user-only and goes through run.sh', 'disable-model-invocation: true' in skill and 'scripts/run.sh' in skill and 'subagents-init' in skill)

    tools = runners()
    check('at least one tool can run here', bool(tools))
    def one_tool(name, make):   # one full pass for one runner; the sh and the PowerShell pass are independent, so they run at the same time
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

            # a project's own SUBAGENTS.md is kept with -Keep
            own = b'# My roster\n\nmine\n\n## Project facts\n\n- layout: src/\n'
            (proj / 'SUBAGENTS.md').write_bytes(own)
            rc, lines, err = step('exists', '-Keep')
            check(f'[{name}] differing SUBAGENTS.md is kept with -Keep', rc == 0 and read(proj / 'SUBAGENTS.md') == own and 'EXISTS SUBAGENTS.md differs from the shipped version; kept as it is (-Keep)' in lines and not list(proj.glob('SUBAGENTS.md.bak-*')), str(lines))

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

        # the default refreshes a differing SUBAGENTS.md (no flag needed): shipped text above, the project's facts kept, one backup
        with tempfile.TemporaryDirectory() as td:
            proj = pathlib.Path(td) / 'p'
            proj.mkdir()
            own = b'# My roster\n\nold text\n\n## Project facts\n\n- layout: src/\n'
            (proj / 'SUBAGENTS.md').write_bytes(own)
            (proj / 'CLAUDE.md').write_bytes(b'# C\n')
            rc, lines, err = run(make, proj)
            log.append(('default-refresh', rc, [re.sub(r'bak-\d{8}T\d{6}Z', 'bak-STAMP', l) for l in lines]))
            new = read(proj / 'SUBAGENTS.md')
            baks = list(proj.glob('SUBAGENTS.md.bak-*'))
            check(f'[{name}] default run: a differing SUBAGENTS.md is refreshed, project facts kept', rc == 0 and new.endswith(b'## Project facts\n\n- layout: src/\n') and new.split(b'## Project facts')[0].replace(b'\r\n', b'\n') == tmpl.split(b'## Project facts')[0] and any(l.startswith('UPDATED SUBAGENTS.md (previous version: SUBAGENTS.md.bak-') for l in lines), str(lines))
            check(f'[{name}] default run: one backup holds the previous file', len(baks) == 1 and baks[0].read_bytes() == own, str(baks))
            rc, lines, err = run(make, proj)
            check(f'[{name}] default run twice: nothing changes, no second backup', rc == 0 and read(proj / 'SUBAGENTS.md') == new and len(list(proj.glob('SUBAGENTS.md.bak-*'))) == 1 and 'UNCHANGED SUBAGENTS.md (shipped part already up to date)' in lines, str(lines))
        with tempfile.TemporaryDirectory() as td:
            proj = pathlib.Path(td) / 'p'
            proj.mkdir()
            (proj / 'SUBAGENTS.md').write_bytes(b'# no marker\n')
            rc, lines, err = run(make, proj)
            check(f'[{name}] default run: a SUBAGENTS.md without a Project facts section is kept (not refused), with a note', rc == 0 and read(proj / 'SUBAGENTS.md') == b'# no marker\n' and not list(proj.glob('SUBAGENTS.md.bak-*')) and any(l.startswith('EXISTS SUBAGENTS.md differs') and 'cannot be refreshed safely' in l for l in lines), str(lines) + err)

        # AGENTS.md only: import goes there, text above it stays byte for byte, a missing final newline is handled
        with tempfile.TemporaryDirectory() as td:
            proj = pathlib.Path(td) / 'p'
            proj.mkdir()
            original = b'# Agents\n\nuse tabs\n\xc3\xa9 no final newline'
            (proj / 'AGENTS.md').write_bytes(original)
            rc, lines, err = step_run = run(make, proj)
            body = read(proj / 'AGENTS.md')
            check(f'[{name}] AGENTS.md only: import added there, CLAUDE.md not created', rc == 0 and not (proj / 'CLAUDE.md').exists() and body.startswith(original) and body.count(b'@SUBAGENTS.md') == 1 and body.count(BEGIN) == 1 and body.endswith(END + b'\n'), repr(body))
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
        orchestration(name, make, log)
        return log

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        transcripts = dict(zip(tools, ex.map(lambda kv: one_tool(*kv), tools.items())))

    if len(transcripts) == 2:
        check('sh and ps1 print identical lines for every scenario', transcripts['sh'] == transcripts['ps1'], f"{transcripts['sh']}\n{transcripts['ps1']}")


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
