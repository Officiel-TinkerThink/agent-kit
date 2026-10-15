"""Turn an annotated agent failure into a benchmark case file.

  python capture_case.py --annotation ann-... --slug blocked-no-run --prompt-file prompt.txt --fixture-dir ./fixture \\
      --rule-broken "Run exactly ONE command..." --expect-all "3/3 passed" --forbid "BLOCKED" --confirm-no-sensitive-data

The annotation (written by the annotator agent; found in <KIT_DATA>/eval/annotations.jsonl) supplies the agent, the failure code, what went wrong and the version.
YOU supply what the annotation cannot: a SYNTHETIC fixture and prompt that reproduce the failure (never copy real project files or the real prompt), and checks the
failed answer would not have passed. Nothing is written when the case fails validation or the privacy scan. Review the written file before you commit it.
"""
import argparse
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casefmt  # noqa: E402


def kit_data():
    d = os.environ.get('AGENT_KIT_DATA')
    if not d:
        c = os.environ.get('CLAUDE_CONFIG_DIR') or str(pathlib.Path.home() / '.claude')
        d = str(pathlib.Path(c) / 'agent-kit')
    return pathlib.Path(d)


def find_annotation(ann_id):
    f = kit_data() / 'eval' / 'annotations.jsonl'
    if not f.exists():
        return None
    found = None
    for line in f.read_text(encoding='utf-8').splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('annotation_id') == ann_id:
            found = d   # the last record with the id wins
    return found


def read_fixture(folder):
    files = {}
    root = pathlib.Path(folder).resolve()
    for f in sorted(root.rglob('*')):
        if f.is_file():
            rel = f.relative_to(root).as_posix()
            try:
                files[rel] = f.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                raise SystemExit(f'REFUSED: fixture file {rel} is not text')
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--annotation', required=True)
    ap.add_argument('--slug', required=True, help='short lower-case words joined by dashes')
    ap.add_argument('--prompt-file', required=True, help='the synthetic task prompt; {kit_data} is replaced by a temp folder at run time')
    ap.add_argument('--fixture-dir', required=True, help='folder of synthetic files the agent works on')
    ap.add_argument('--rule-broken', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('--symptom', default='', help='what the agent did wrong; defaults to the annotation summary')
    ap.add_argument('--expect-all', action='append', default=[])
    ap.add_argument('--expect-any', action='append', default=[])
    ap.add_argument('--forbid', action='append', default=[])
    ap.add_argument('--require-regex', action='append', default=[])
    ap.add_argument('--forbid-regex', action='append', default=[])
    ap.add_argument('--min-turns', type=int, default=0)
    ap.add_argument('--allow', action='append', default=[], help='tool permission for the run, e.g. "Bash(python check.py)" (repeatable)')
    ap.add_argument('--note', default='')
    ap.add_argument('--confirm-no-sensitive-data', action='store_true', help='you checked that the case holds no real project data, secrets or personal data')
    a = ap.parse_args()
    if not a.confirm_no_sensitive_data:
        print('REFUSED: the case will be committed to a public branch. Check the prompt, fixture and symptom for real project data, secrets and personal data, then add --confirm-no-sensitive-data.', file=sys.stderr)
        return 2
    ann = find_annotation(a.annotation)
    if not ann:
        print(f'REFUSED: annotation {a.annotation} not found in {kit_data() / "eval" / "annotations.jsonl"}', file=sys.stderr)
        return 2
    if ann.get('verified') == 'no':
        print('REFUSED: the annotator could not confirm this failure (verified: no); it is not a benchmark case', file=sys.stderr)
        return 2
    agent = str(ann.get('agent_type', '')).split(':')[-1]
    agents = casefmt.agent_names()
    if agent not in agents:
        print(f'REFUSED: annotation is about {agent!r}, which is not an agent of this checkout (renamed or merged? name the new agent in the annotation or edit the case)', file=sys.stderr)
        return 2
    ver = json.loads((agents[agent].parents[1] / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']
    checks = {k: v for k, v in (('expect_all', a.expect_all), ('expect_any', a.expect_any), ('forbid', a.forbid), ('require_regex', a.require_regex), ('forbid_regex', a.forbid_regex)) if v}
    if a.min_turns:
        checks['min_turns'] = a.min_turns
    case = {
        'schema': casefmt.SCHEMA, 'id': f'BC-{agent}-{a.slug}', 'agent': agent, 'title': a.title or (ann.get('summary') or '')[:100], 'found_in': ver, 'status': 'open',
        'origin': {'type': 'annotation', 'annotation_id': a.annotation},
        'failure': {'code': ann.get('code'), 'rule_broken': a.rule_broken, 'symptom': (a.symptom or ann.get('summary') or '')[:500]},
        'prompt': pathlib.Path(a.prompt_file).read_text(encoding='utf-8').strip(),
        'fixture': {'files': read_fixture(a.fixture_dir)}, 'checks': checks,
    }
    if a.allow:
        case['allow'] = a.allow
    if a.note:
        case['note'] = a.note
    probs = casefmt.validate(case)
    if probs:
        print('REFUSED:\n  ' + '\n  '.join(probs), file=sys.stderr)
        return 2
    out = casefmt.CASES_DIR / agent / f"{case['id']}.json"
    if out.exists():
        print(f'REFUSED: {out} exists; choose another --slug', file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(case, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(f'CREATED {out}\nNext: read the file, run `python run_cases.py run --cases {case["id"]} --reps 3` (the failing agent should fail it), then commit it to the bench-cases branch.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
