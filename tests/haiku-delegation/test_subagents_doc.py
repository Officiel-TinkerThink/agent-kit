"""SUBAGENTS.md must list every shipped agent, and must not name an agent that does not exist. Run: python test_subagents_doc.py"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOC = (ROOT / 'SUBAGENTS.md').read_text(encoding='utf-8')
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    agents = {f.stem: f.parent.parent.name for f in sorted((ROOT / 'plugins').glob('*/agents/*.md'))}
    check('agents found', len(agents) >= 29, str(len(agents)))
    # an agent counts as listed when it appears as `name` inside a table row of the doc
    rows = [line for line in DOC.splitlines() if line.startswith('|')]
    for name in agents:
        check(f'{name}: has a row in SUBAGENTS.md', any(f'`{name}`' in r.split('|')[2] if len(r.split('|')) > 2 else False for r in rows) or any(f'`{name}`' in r for r in rows), 'missing')
    # backticked names in the first column of the roster tables that look like agent names must exist
    first_cols = []
    for r in rows:
        cells = r.split('|')
        if len(cells) > 3:
            first_cols += re.findall(r'`([a-z][a-z0-9-]+)`', cells[2])   # the Agent column
    unknown = sorted({n for n in first_cols if n not in agents and '-' in n and n not in ('last:<agent_type>',)})
    check('every agent named in an Agent column exists', not unknown, ', '.join(unknown))
    check('has the sections a project needs', all(h in DOC for h in ('## Stance', '## Writing a brief', '## Close-out', '## Project facts')))
    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
