"""The code-review agents must be read-only Haiku 5.5 agents with the kit's operating rules, a turn cap of 3 x their budget, a LENS check and the skills they preload;
each skill must exist, carry its LENS-MARKER, stay small, stay ASCII and keep the catalog shape; the orchestration skill must name only agents that exist.
Run: python test_agents.py"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'plugins' / 'code-review'
results = []
REVIEWERS = ['spec-reviewer', 'defect-reviewer', 'architecture-reviewer', 'security-reviewer', 'guidance-reviewer', 'history-reviewer', 'simplicity-reviewer']
ALL = REVIEWERS + ['finding-validator']
COMPANION_LENSES = {}
LENS_OF = {'spec-reviewer': 'spec-lens', 'defect-reviewer': 'defect-lens', 'architecture-reviewer': 'architecture-lens', 'security-reviewer': 'security-lens',
           'guidance-reviewer': 'guidance-lens', 'history-reviewer': 'history-lens', 'simplicity-reviewer': 'simplicity-lens', 'finding-validator': 'validator-lens'}
SKILLS = ['review-craft', 'spec-lens', 'defect-lens', 'architecture-lens', 'security-lens', 'guidance-lens', 'history-lens', 'simplicity-lens', 'validator-lens']
CATALOG_LENSES = ['spec-lens', 'defect-lens', 'architecture-lens', 'security-lens', 'guidance-lens', 'history-lens', 'simplicity-lens']


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def frontmatter(text):
    text = text.replace('\r\n', '\n')
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    fields = {}
    if m:
        last = None
        for line in m.group(1).splitlines():
            if line.startswith('  - ') and last is not None:
                fields.setdefault(last, [])
                if isinstance(fields[last], list):
                    fields[last].append(line[4:].strip())
                continue
            k, _, v = line.partition(':')
            last = k.strip()
            v = v.strip().strip('"')
            fields[last] = v if v else []
    return fields, text[m.end():] if m else text


def budgets():
    rows = {}
    for line in (ROOT / 'plugins' / 'agent-guards' / 'scripts' / 'turn-budget.txt').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            a, n = line.split()
            rows[a] = int(n)
    return rows


def main():
    plugin = json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
    check('plugin name is code-review', plugin['name'] == 'code-review')
    found = sorted(p.stem for p in (PLUGIN / 'agents').glob('*.md'))
    check('the eight agents exist and no others', found == sorted(ALL), str(found))
    rows = budgets()
    for name in ALL:
        raw = (PLUGIN / 'agents' / (name + '.md')).read_text(encoding='utf-8')
        fm, body = frontmatter(raw)
        check(f'{name}: name matches file', fm.get('name') == name, str(fm))
        check(f'{name}: pinned to claude-haiku-5-5', fm.get('model') == 'claude-haiku-5-5', str(fm.get('model')))
        check(f'{name}: read-only tools', fm.get('tools') == 'Read, Grep, Glob', str(fm.get('tools')))
        check(f'{name}: omitClaudeMd', fm.get('omitClaudeMd') == 'true')
        check(f'{name}: has an effort tier', fm.get('effort') in ('low', 'medium', 'high'), str(fm.get('effort')))
        check(f'{name}: description starts with Use proactively', str(fm.get('description', '')).startswith('Use proactively'))
        check(f'{name}: description does not tell the agent to run the validator itself', 'do not act on a finding that has no validator verdict' in str(fm.get('description', '')) or name == 'finding-validator')
        m = re.search(r'- Turn budget: you have about (\d+) tool calls\.', body)
        n = int(m.group(1)) if m else -1
        check(f'{name}: turn budget text, a row in turn-budget.txt and maxTurns = 3 x budget', m is not None and rows.get(name) == n and str(fm.get('maxTurns')) == str(3 * n), f'{n} {rows.get(name)} {fm.get("maxTurns")}')
        check(f'{name}: budget rule mentions PARTIAL', 'PARTIAL' in body)
        for rule in ('Data, not instructions', 'Read-only: never create', '- One unit: your brief is one unit of work', 'NOT DONE (send each to its own agent)', 'Tools work', '- Lens check:'):
            check(f'{name}: has the rule "{rule}"', rule in body)
        check(f'{name}: lens example names no real marker', not re.search(r'[a-z]+-(lens|craft) v1', body))
        skills = fm.get('skills')
        expected = ['review-craft', LENS_OF[name]] + COMPANION_LENSES.get(name, [])
        check(f'{name}: preloads review-craft, {LENS_OF[name]} and its companions', skills == expected, str(skills))
        check(f'{name}: no verdicts on compliance', 'No verdicts' in body or 'never add findings' in body)
        check(f'{name}: ASCII only', all(ord(c) < 128 for c in raw))
    for name in REVIEWERS:
        body = frontmatter((PLUGIN / 'agents' / (name + '.md')).read_text(encoding='utf-8'))[1]
        check(f'{name}: neutral stance and NO FINDINGS is allowed', 'Stance: neutral' in body and 'NO FINDINGS' in body)
        check(f'{name}: findings need a quoted line and a scenario or path', 'quote:' in body and ('scenario:' in body or 'path:' in body))
        check(f'{name}: states a scope rule and a do-not-report list', 'Scope' in body and 'Do not report' in body)
        check(f'{name}: confidence floor is 50', 'confidence: <50-100>' in body)
        check(f'{name}: severity points at the review-craft scale', 'Severity: use the review-craft scale' in body)
    val = (PLUGIN / 'agents' / 'finding-validator.md').read_text(encoding='utf-8')
    for needle in ('CONFIRMED', 'REFUTED', 'UNVERIFIABLE', 'Missing-code findings', 'Never refute a missing-code finding because the quote is `none`', 'REASON:',
                   'NOT A DEFECT', 'INCOMPLETE SEARCH', 'Absolutely certain', 'never search a parent folder'):
        check(f'finding-validator: contains "{needle}"', needle in val)

    for skill in SKILLS:
        path = PLUGIN / 'skills' / skill / 'SKILL.md'
        check(f'skill {skill}: exists', path.is_file())
        if not path.is_file():
            continue
        raw = path.read_text(encoding='utf-8')
        fm, body = frontmatter(raw)
        lines = raw.count('\n') + 1
        check(f'skill {skill}: frontmatter is exactly name, description, user-invocable false', sorted(fm) == ['description', 'name', 'user-invocable'] and fm.get('name') == skill and fm.get('user-invocable') == 'false', str(sorted(fm)))
        check(f'skill {skill}: carries its LENS-MARKER', f'LENS-MARKER: {skill} v1' in raw)
        check(f'skill {skill}: at most 400 lines', lines <= 400, str(lines))
        check(f'skill {skill}: ASCII only', all(ord(c) < 128 for c in raw))
        if skill in CATALOG_LENSES:
            entries = len(re.findall(r'(?m)^### ', raw))
            counts = {k: len(re.findall(r'(?m)^(?:- )?' + k, raw)) for k in ('Tell:', 'Fails when:', 'Not a defect when:')}
            check(f'skill {skill}: every catalog entry has Tell, Fails when and Not a defect when', entries > 0 and all(c == entries for c in counts.values()), f'{entries} {counts}')
            for h in ('## How to look', '## Catalog', '## Known safe patterns', '## Do not report'):
                check(f'skill {skill}: has "{h}"', h in raw)
    skill = (PLUGIN / 'skills' / 'review' / 'SKILL.md').read_text(encoding='utf-8')
    check('review skill has a description', str(frontmatter(skill)[0].get('description', '')) != '')
    named = set(re.findall(r'code-review:([a-z-]+)', skill))
    check('review skill names only agents that exist', named <= set(ALL), str(named - set(ALL)))
    check('review skill names every agent', set(ALL) <= named, str(set(ALL) - named))
    for needle in ('Step 0', 'waves of at most 8 agents', 'never merge across axes', 'Never drop silently'.lower(), 'evidence only', 'LENS:', 'also-seen', 'Change scope'):
        check(f'review skill: contains "{needle}"', needle.lower() in skill.lower())
    readme = (ROOT / 'benchmarks' / 'code-review' / 'README.md').read_text(encoding='utf-8')
    check('benchmark README states the critique, optimise, revise principle', '## Principle: critique, optimise, revise' in readme and 'benchmark-leak-auditor' in readme)
    auditor = (ROOT / '.claude' / 'agents' / 'benchmark-leak-auditor.md').read_text(encoding='utf-8')
    check('benchmark-leak-auditor exists and is read-only', 'tools: Read, Grep, Glob' in auditor and 'model: claude-haiku-5-5' in auditor)
    market = json.loads((ROOT / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
    entry = [e for e in market['plugins'] if e['name'] == 'code-review']
    check('marketplace lists code-review at the plugin version', len(entry) == 1 and entry[0]['version'] == plugin['version'] and entry[0]['source'] == './plugins/code-review', str(entry))
    check('CHANGELOG mentions the plugin', 'code-review:finding-validator' in (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'))


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
