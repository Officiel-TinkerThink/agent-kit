"""bench-case/1: one agent failure kept as a repeatable benchmark case. Validation, privacy scan and scoring; no model calls.

A case is a task an agent of this kit failed (broke a rule, missed the expectation), rewritten so that anyone can run it: a small synthetic fixture,
the prompt, and checks that the failed answer would not have passed. It never holds a real transcript, real project files, secrets or personal data.
"""
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES_DIR = pathlib.Path(os.environ.get('BENCH_CASES_DIR') or (pathlib.Path(__file__).resolve().parent / 'cases'))   # BENCH_CASES_DIR: tests and other checkouts
SCHEMA = 'bench-case/1'
ID_RE = re.compile(r'^BC-[a-z0-9]+(-[a-z0-9]+){1,8}$')
CODES = {'fabricated_fact', 'wrong_count', 'omission', 'wrong_line_citation', 'rule_violation', 'format_noncompliant', 'verdict_given', 'secret_exposed',
         'scope_creep', 'tool_misuse', 'misread_source', 'other'}
STATUSES = {'open', 'fixed'}
LIMITS = {'title': 120, 'prompt': 4000, 'rule_broken': 300, 'symptom': 500, 'note': 500, 'fixture_files': 20, 'fixture_bytes': 20000, 'check_items': 20, 'check_len': 300}
# things that must never be stored in a public case
SECRETS = re.compile(r'(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|xox[a-z]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{12,}|AIza[A-Za-z0-9_-]{20,}|'
                     r'-----BEGIN [A-Z ]*PRIVATE KEY-----|://[^/@\s]+:[^/@\s]+@|(?i:password|passwd|secret|api[_-]?key|token)\s*[=:]\s*[\'"]?[A-Za-z0-9+/_-]{12,})')
PRIVATE = re.compile(r'([A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+|/Users/[^/\s]+|/home/[^/\s]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')
SAFE_REL = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_./-]{0,120}$')


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings(k)
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def privacy_problems(case):
    """text in a case that looks like a secret or personal data (kinds only, never the text)"""
    found = set()
    for s in strings(case):
        if SECRETS.search(s):
            found.add('secret-shaped text')
        if PRIVATE.search(s):
            found.add('home path or e-mail address')
    return sorted(found)


def agent_names():
    out = {}
    for f in (ROOT / 'plugins').glob('*/agents/*.md'):
        out[f.stem] = f
    return out


def validate(case, known_agents=None):
    """list of problems, empty when the case is acceptable"""
    p = []
    if not isinstance(case, dict):
        return ['case is not a JSON object']
    case = {k: v for k, v in case.items() if not str(k).startswith('_')}   # loader bookkeeping such as _file (a local path) is not part of the case
    if case.get('schema') != SCHEMA:
        p.append(f'schema must be {SCHEMA}')
    if not isinstance(case.get('id'), str) or not ID_RE.match(case.get('id', '')):
        p.append('id must look like BC-<agent>-<slug> (lower case letters, digits, dashes)')
    agents = known_agents if known_agents is not None else agent_names()
    if case.get('agent') not in agents:
        p.append(f"agent {case.get('agent')!r} is not an agent of this kit")
    elif isinstance(case.get('id'), str) and not case['id'].startswith('BC-'):
        pass
    for k, lim in (('title', 'title'), ('prompt', 'prompt')):
        v = case.get(k)
        if not isinstance(v, str) or not v.strip():
            p.append(f'{k} is required')
        elif len(v) > LIMITS[lim]:
            p.append(f'{k} is longer than {LIMITS[lim]} characters')
    if not re.fullmatch(r'\d+\.\d+\.\d+', str(case.get('found_in', ''))):
        p.append('found_in must be a version such as 0.2.0')
    if case.get('status') not in STATUSES:
        p.append('status must be open or fixed')
    if case.get('status') == 'fixed' and not re.fullmatch(r'\d+\.\d+\.\d+', str(case.get('fixed_in', ''))):
        p.append('a fixed case needs fixed_in (a version)')
    o = case.get('origin')
    if not isinstance(o, dict) or o.get('type') not in ('annotation', 'manual'):
        p.append('origin.type must be annotation or manual')
    elif o.get('type') == 'annotation' and not re.fullmatch(r'ann-[A-Za-z0-9-]{6,60}', str(o.get('annotation_id', ''))):
        p.append('origin.annotation_id must be an annotation id (ann-...)')
    f = case.get('failure')
    if not isinstance(f, dict):
        p.append('failure is required: {code, rule_broken, symptom}')
    else:
        if f.get('code') not in CODES:
            p.append('failure.code must be one of the annotation codes')
        for k in ('rule_broken', 'symptom'):
            if not isinstance(f.get(k), str) or not f[k].strip():
                p.append(f'failure.{k} is required')
            elif len(f[k]) > LIMITS[k]:
                p.append(f'failure.{k} is longer than {LIMITS[k]} characters')
    fx = case.get('fixture')
    if not isinstance(fx, dict) or not isinstance(fx.get('files'), dict):
        p.append('fixture.files is required (it may be empty)')
    else:
        files = fx['files']
        if len(files) > LIMITS['fixture_files']:
            p.append(f"fixture has more than {LIMITS['fixture_files']} files")
        total = 0
        for rel, text in files.items():
            if not SAFE_REL.match(rel) or '..' in rel.split('/') or rel.startswith('/'):
                p.append(f'fixture path {rel!r} is not a safe relative path')
            if not isinstance(text, str):
                p.append(f'fixture file {rel!r} must be text')
            else:
                total += len(text.encode('utf-8'))
        if total > LIMITS['fixture_bytes']:
            p.append(f"fixture is larger than {LIMITS['fixture_bytes']} bytes")
    c = case.get('checks')
    if not isinstance(c, dict):
        p.append('checks is required')
    else:
        unknown = set(c) - {'expect_all', 'expect_any', 'forbid', 'require_regex', 'forbid_regex', 'min_turns'}
        if unknown:
            p.append(f'unknown checks: {sorted(unknown)}')
        for k in ('expect_all', 'expect_any', 'forbid', 'require_regex', 'forbid_regex'):
            v = c.get(k, [])
            if not isinstance(v, list) or any(not isinstance(x, str) or not x or len(x) > LIMITS['check_len'] for x in v) or len(v) > LIMITS['check_items']:
                p.append(f'checks.{k} must be a list of at most {LIMITS["check_items"]} short strings')
            elif k.endswith('regex'):
                for x in v:
                    try:
                        re.compile(x)
                    except re.error:
                        p.append(f'checks.{k} has an invalid regular expression: {x[:40]}')
        if 'min_turns' in c and not (isinstance(c['min_turns'], int) and 1 <= c['min_turns'] <= 50):
            p.append('checks.min_turns must be a whole number from 1 to 50')
        if not any(c.get(k) for k in ('expect_all', 'expect_any', 'require_regex', 'min_turns')) and not c.get('forbid') and not c.get('forbid_regex'):
            p.append('checks cannot fail: add at least one expectation or one forbidden text')
    al = case.get('allow')
    if al is not None and (not isinstance(al, list) or any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z_]+(\([^()\n]{1,80}\))?', x) for x in al)):
        p.append('allow must be a list of tool names such as Read or Bash(python check.py)')
    if 'note' in case and (not isinstance(case['note'], str) or len(case['note']) > LIMITS['note']):
        p.append(f"note must be text of at most {LIMITS['note']} characters")
    for kind in privacy_problems(case):
        p.append(f'case contains {kind}; replace it with synthetic text')
    return p


def score(case, answer, turns=None):
    """(ok, notes) for one answer"""
    c = case['checks']
    notes = []
    a = answer or ''
    for x in c.get('expect_all', []):
        if x not in a:
            notes.append(f'missing: {x}')
    if c.get('expect_any') and not any(x in a for x in c['expect_any']):
        notes.append('none of: ' + ' | '.join(c['expect_any']))
    for x in c.get('forbid', []):
        if x in a:
            notes.append(f'forbidden text present: {x}')
    for x in c.get('require_regex', []):
        if not re.search(x, a, re.M):
            notes.append(f'no match: {x}')
    for x in c.get('forbid_regex', []):
        if re.search(x, a, re.M):
            notes.append(f'forbidden pattern matched: {x}')
    if c.get('min_turns') and (turns is None or turns < c['min_turns']):
        notes.append(f"ran {turns} turn(s), at least {c['min_turns']} needed (the agent must act, not only answer)")
    return (not notes), notes


def load_dir(path=None):
    """{id: case} for every case file below the cases folder; raises ValueError on a file that is not JSON"""
    out = {}
    for f in sorted(pathlib.Path(path or CASES_DIR).glob('*/*.json')):
        try:
            c = json.loads(f.read_text(encoding='utf-8'))
        except ValueError as e:
            raise ValueError(f'{f}: not valid JSON ({e})')
        c['_file'] = str(f)
        out[c.get('id', f.stem)] = c
    return out
