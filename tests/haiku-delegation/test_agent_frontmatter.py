"""Every agent file's YAML frontmatter must parse. Claude Code silently drops the WHOLE frontmatter of an agent that fails to parse
(name from the file name, no model, no effort, no tool limits). Run: python test_agent_frontmatter.py"""
import pathlib
import re
import sys

PLUGINS = pathlib.Path(__file__).resolve().parents[2] / 'plugins'
REQUIRED = ('name', 'description')
results = []

try:
    import yaml
except ImportError:
    yaml = None


def frontmatter(text):
    m = re.match(r'^﻿?---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
    return m.group(1) if m else None


def lint_plain_scalars(fm):
    """Fallback without PyYAML: an unquoted value must not contain ': ' or ' #', or start with a YAML indicator."""
    problems = []
    for line in fm.splitlines():
        m = re.match(r'^([A-Za-z][\w-]*):\s*(.*)$', line)
        if not m:
            continue
        key, val = m.groups()
        if not val or val[0] in '"\'[{|>':
            continue
        if ': ' in val or ' #' in val or val[0] in '&*!%@`':
            problems.append(f"{key}: unquoted value contains ': ' or ' #' (quote it)")
    return problems


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    files = sorted(PLUGINS.glob('*/agents/*.md'))
    check('agent files found', len(files) >= 12, str(len(files)))
    for f in files:
        rel = f.relative_to(PLUGINS)
        fm = frontmatter(f.read_text(encoding='utf-8'))
        if fm is None:
            check(f'{rel}: has frontmatter', False)
            continue
        problems = lint_plain_scalars(fm)
        data = None
        if yaml is not None:
            try:
                data = yaml.safe_load(fm)
            except yaml.YAMLError as e:
                problems.append(f'YAML parse error: {str(e).splitlines()[0]}')
        if data is not None:
            if not isinstance(data, dict):
                problems.append('frontmatter is not a mapping')
            else:
                problems += [f'missing {k}' for k in REQUIRED if not data.get(k)]
                if data.get('name') and data['name'] != f.stem:
                    problems.append(f"name '{data['name']}' differs from the file name")
        check(f'{rel}: frontmatter parses', not problems, '; '.join(problems))
    print(f'\n{sum(results)}/{len(results)} passed' + ('' if yaml else '  (PyYAML not installed: plain-scalar lint only)'))
    sys.exit(0 if all(results) else 1)


main()
