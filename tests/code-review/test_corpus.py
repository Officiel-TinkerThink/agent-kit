"""The code-review benchmark corpus: every answer key parses, every cited line exists in its case, clean cases have no defects, no answer key
sits inside a case folder, and no case file names the answer key. Run: python test_corpus.py"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCH = ROOT / 'benchmarks' / 'code-review'
CASES = BENCH / 'cases'
TRUTH = BENCH / 'truth'
results = []
EXPECTED = {'spec': 10, 'design': 11, 'security': 9, 'guidance': 8, 'history': 8, 'bug': 6, 'simplicity': 5}


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    for axis, n in EXPECTED.items():
        keys = sorted((TRUTH / axis).glob('*.json'))
        check(f'{axis}: {n} answer keys', len(keys) == n, str([k.name for k in keys]))
        for key in keys:
            case = key.stem
            data = json.loads(key.read_text(encoding='utf-8'))
            folder = CASES / axis / case
            check(f'{case}: case folder exists', folder.is_dir())
            check(f'{case}: axis and case fields match', data.get('axis') == axis and data.get('case') == case, str({k: data.get(k) for k in ('axis', 'case')}))
            check(f'{case}: has defects and decoys lists', isinstance(data.get('defects'), list) and isinstance(data.get('decoys'), list))
            for kind in ('defects', 'decoys'):
                for item in data.get(kind, []):
                    f = folder / item['file']
                    ok = f.is_file()
                    if ok:
                        lines = f.read_text(encoding='utf-8').splitlines()
                        ok = 1 <= item['line'] <= len(lines)
                    check(f'{case}: {kind[:-1]} {item.get("id", "decoy")} cites an existing line {item["file"]}:{item["line"]}', ok)
            if not data['defects']:
                check(f'{case}: clean case has at least two decoys', len(data['decoys']) >= 2, str(len(data['decoys'])))
            if '-h' in case:
                check(f'{case}: hard case has difficulty, base folder and a non-empty change.diff', data.get('difficulty') == 'hard' and (folder / 'base').is_dir()
                      and (folder / 'change.diff').is_file() and (folder / 'change.diff').stat().st_size > 0)
                check(f'{case}: hard case has a preexisting decoy outside the diff', any(d.get('kind') == 'preexisting' for d in data['decoys']))
                for d in data['defects']:
                    check(f'{case}: defect {d["id"]} says whether it is in the diff and cross-file', 'in_diff' in d and 'cross_file' in d)
    check('no answer key inside a case folder', not list(CASES.rglob('truth.json')) and not list(CASES.rglob('*truth*')))
    leaks = []
    for f in CASES.rglob('*'):
        if f.is_file() and f.suffix in ('.py', '.md', '.txt', '.diff'):
            if re.search(r'(?i)\b(truth|answer key|decoy|seeded)\b', f.read_text(encoding='utf-8')):
                leaks.append(str(f.relative_to(CASES)))
    check('no case file names the answer key, a decoy or a seeded defect', not leaks, str(leaks))


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
