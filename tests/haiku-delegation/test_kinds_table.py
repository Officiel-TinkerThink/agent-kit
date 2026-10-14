"""kinds.txt is the one table of the kinds of each topic agent. The copy in agent-eval must equal the one in haiku-delegation, every row must name an existing agent and
a section `## <kind>:` in that agent's file, every such section must have a row, and the footers column must use known words. Run: python test_kinds_table.py"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'plugins' / 'haiku-delegation' / 'scripts' / 'kinds.txt'
COPY = ROOT / 'plugins' / 'agent-eval' / 'scripts' / 'kinds.txt'
AGENTS = ROOT / 'plugins' / 'haiku-delegation' / 'agents'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    check('both copies exist', SRC.is_file() and COPY.is_file())
    check('the agent-eval copy equals the haiku-delegation table', SRC.read_bytes() == COPY.read_bytes())
    rows = []
    for n, line in enumerate(SRC.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        f = line.split()
        check(f'row {n} has four fields', len(f) == 4, line)
        if len(f) == 4:
            rows.append(f)
            check(f'row {n} ({f[0]} {f[1]}): agent and kind are plain lower-case words', all(re.fullmatch(r'[a-z][a-z0-9-]*', x) for x in f[:2]), line)
            check(f'row {n}: effort is low, medium, high or max', f[3] in ('low', 'medium', 'high', 'max'), f[3])
            check(f'row {n}: footers are - or known words', f[2] == '-' or set(f[2].split(',')) <= {'coverage', 'reconciliation'}, f[2])
    check('no duplicate rows', len({(r[0], r[1]) for r in rows}) == len(rows))
    by_agent = {}
    for a, k, _, _ in rows:
        by_agent.setdefault(a, set()).add(k)
    for agent, kinds in sorted(by_agent.items()):
        f = AGENTS / f'{agent}.md'
        check(f'{agent}: agent file exists', f.is_file(), str(f))
        if not f.is_file():
            continue
        sections = set(re.findall(r'^## ([a-z][a-z0-9-]*):', f.read_text(encoding='utf-8'), re.M))
        check(f'{agent}: every kind has a section', kinds <= sections, f'missing sections: {sorted(kinds - sections)}')
        check(f'{agent}: every section has a kind row', sections <= kinds, f'sections without a row: {sorted(sections - kinds)}')
    print(f'\n{sum(results)}/{len(results)} passed')
    sys.exit(0 if all(results) else 1)


main()
