"""/subagents-init: copies SUBAGENTS.md to a project, imports it from CLAUDE.md or AGENTS.md and adds the shipped AGENTS.md text there as a marked block, without overwriting anything.
The scenarios are recorded in cases/subagents-init.json (each case is one project folder with ordered runs, see tests/golden.py) and replayed through each
implementation that runs here (the PowerShell and the POSIX sh tool); the backup time stamps and the ROOT line are masked there. The shipped templates and the
skill are checked here. Run: python test_subagents_init.py"""
import pathlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden  # noqa: E402
from capability import summary  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'plugins' / 'haiku-delegation'
SCRIPTS = PLUGIN / 'scripts'
CASES = Path(__file__).resolve().parent / 'cases'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    shipped = (ROOT / 'SUBAGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    tmpl = (PLUGIN / 'templates' / 'SUBAGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    check('shipped template equals the repo SUBAGENTS.md (copy it again after editing the root file)', shipped == tmpl)
    check('template has a Project facts section and the annotator duty', b'\n## Project facts' in tmpl and b'Report agent failures to the annotator' in tmpl)
    ag_root = (ROOT / 'AGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    ag_tmpl = (PLUGIN / 'templates' / 'AGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    check('shipped AGENTS.md template equals the repo AGENTS.md (copy it again after editing the root file)', ag_root == ag_tmpl)
    check('AGENTS.md template is the orchestrator text and holds no marker text', ag_tmpl.startswith(b'# Orchestrator-First Execution') and b'agent-kit:orchestration' not in ag_tmpl)
    skill = (PLUGIN / 'skills' / 'subagents-init' / 'SKILL.md').read_text(encoding='utf-8')
    check('skill is user-only and goes through run.sh', 'disable-model-invocation: true' in skill and 'scripts/run.sh' in skill and 'subagents-init' in skill)

    golden.replay(CASES / 'subagents-init.json', SCRIPTS / 'subagents-init', results, check)
    print(summary(results))
    sys.exit(0 if all(results) else 1)


main()
