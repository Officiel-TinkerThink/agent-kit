"""Benchmark harness for the code-review plugin.

run   : for every case, start a headless Claude Code session that loads the plugin with --plugin-dir, calls the matching code-review agent once,
        and saves the agent's full answer to results/<arm>/<case>.md. At most --workers sessions run at the same time (default 8).
        arm "skills"   = the plugin as shipped (each agent preloads its skills).
        arm "baseline" = a temporary copy of the plugin with every `skills:` block removed from the agent files (same prompts, no lens skills).
score : compare saved reports with truth/<axis>/<case>.json and print recall, extras, clean-case false positives and pre-existing-trap hits.
        A defect counts as found when a finding block cites the same file name within --window lines of the key line. This is a deterministic first pass;
        missing-code defects and re-worded locations still need a human or an independent reviewer (see README).

Usage: python harness.py run --arm skills [--cases hard|all|ID,ID] [--workers 8]
       python harness.py score --arm skills
"""
import argparse
import concurrent.futures
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

BENCH = pathlib.Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
PLUGIN = ROOT / 'plugins' / 'code-review'
CASES = BENCH / 'cases'
TRUTH = BENCH / 'truth'
RESULTS = BENCH / 'results'
AGENT_OF = {'spec': 'spec-reviewer', 'design': 'architecture-reviewer', 'security': 'security-reviewer', 'guidance': 'guidance-reviewer', 'history': 'history-reviewer',
            'bug': 'defect-reviewer', 'simplicity': 'simplicity-reviewer'}
INTENT_LABEL = {'spec': 'Spec', 'design': 'Intent', 'security': 'Intent', 'guidance': 'Intent', 'history': 'Intent', 'bug': 'Intent', 'simplicity': 'Intent'}


def all_cases():
    out = []
    for axis in AGENT_OF:
        for key in sorted((TRUTH / axis).glob('*.json')):
            out.append((axis, key.stem))
    return out


def select(spec):
    cases = all_cases()
    if spec == 'all':
        return cases
    if spec == 'round2':
        return [c for c in cases if c[0] in ('bug', 'simplicity') or re.search(r'-h[4-9]$', c[1])]
    if spec == 'hard':
        return [c for c in cases if '-h' in c[1]]
    wanted = set(spec.split(','))
    return [c for c in cases if c[1] in wanted]


def brief(axis, case):
    folder = CASES / axis / case
    parts = [f'{INTENT_LABEL[axis]}: {folder / "spec.md"}.']
    if axis == 'guidance':
        parts.append(f'Rule files: everything under {folder / "rules"} (a nested rules file governs only the directory it sits in).')
    if axis == 'history':
        parts.append(f'History digest: {folder / "history.txt"}.')
    if (folder / 'change.diff').is_file():
        parts.append(f'This is a review of a CHANGE, mode: diff. The change (diff): {folder / "change.diff"}. Files after the change: all under {folder / "code"}.')
    else:
        parts.append(f'Mode: whole-file. All code under {folder / "code"} is in scope.')
    parts.append('Read only those paths; open nothing under any truth folder and not any base folder. Report in the format your instructions define.')
    return ' '.join(parts)


def prompt(axis, case, agent_map=None):
    agent = (agent_map or {}).get(axis, AGENT_OF[axis])
    return (f'Call the Agent tool exactly once with subagent_type "code-review:{agent}" and this brief:\n\n{brief(axis, case)}\n\n'
            'When the agent has answered, reply with the agent\'s COMPLETE answer copied verbatim, nothing before it and nothing after it. '
            'Do not read any files yourself and do not call any other tool.')


def baseline_plugin(tmp):
    dest = pathlib.Path(tmp) / 'code-review-baseline'
    shutil.copytree(PLUGIN, dest)
    for f in (dest / 'agents').glob('*.md'):
        text = f.read_text(encoding='utf-8').replace('\r\n', '\n')
        text = re.sub(r'(?m)^skills:\n(  - .*\n)+', '', text)
        f.write_text(text, encoding='utf-8', newline='\n')
    return dest


def run_one(plugin_dir, arm, axis, case, agent_map=None, tag=''):
    out_dir = RESULTS / (arm + tag)
    out_dir.mkdir(parents=True, exist_ok=True)
    claude = shutil.which('claude') or 'claude'
    cmd = [claude, '-p', '--model', 'haiku', '--plugin-dir', str(plugin_dir), '--allowedTools', 'Agent,Read,Grep,Glob', '--output-format', 'json']
    p = subprocess.run(cmd, input=prompt(axis, case, agent_map), capture_output=True, text=True, encoding='utf-8', cwd=str(ROOT), timeout=1500)
    text, cost = '', None
    try:
        data = json.loads(p.stdout)
        text, cost = data.get('result', ''), data.get('total_cost_usd')
    except ValueError:
        text = '(no json) ' + p.stdout[-2000:] + p.stderr[-500:]
    (out_dir / f'{case}.md').write_text(text, encoding='utf-8')
    return case, cost, len(text)


def parse_map(text):
    return dict(item.split('=', 1) for item in text.split(',') if item) if text else {}


def cmd_run(a):
    cases = select(a.cases)
    with tempfile.TemporaryDirectory() as tmp:
        plugin_dir = baseline_plugin(tmp) if a.arm == 'baseline' else PLUGIN
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = [ex.submit(run_one, plugin_dir, a.arm, axis, case, parse_map(a.agent_map), a.tag) for axis, case in cases]
            for f in concurrent.futures.as_completed(futs):
                case, cost, n = f.result()
                print(f'{case}: {n} chars, cost {cost}')


def findings(text):
    """Split a report into finding blocks: an F<n> line plus its continuation lines."""
    blocks, cur = [], None
    for line in text.splitlines():
        if re.match(r'^\s*F\d+ \|', line):
            cur = [line]
            blocks.append(cur)
        elif cur is not None and (line.startswith('   ') or line.startswith('\t')):
            cur.append(line)
        else:
            cur = None
    return ['\n'.join(b) for b in blocks]


def cites(block):
    return [(pathlib.PurePosixPath(m.group(1).replace('\\', '/')).name, int(m.group(2))) for m in re.finditer(r'([\w./\\-]+\.(?:py|toml)):(\d+)', block)]


def cmd_score(a):
    tot = {'defects': 0, 'found': 0, 'findings': 0, 'extras': 0, 'trap_hits': 0, 'clean_fp': 0, 'clean': 0, 'clean_ok': 0, 'missing': 0}
    for axis, case in select(a.cases):
        report = RESULTS / (a.arm + a.tag) / f'{case}.md'
        if not report.is_file():
            tot['missing'] += 1
            continue
        truth = json.loads((TRUTH / axis / f'{case}.json').read_text(encoding='utf-8'))
        blocks = findings(report.read_text(encoding='utf-8'))
        used = set()
        found = []
        for d in truth['defects']:
            base, line = pathlib.PurePosixPath(d['file']).name, d['line']
            hit = [i for i, b in enumerate(blocks) if any(f == base and abs(l - line) <= a.window for f, l in cites(b))]
            found.append((d['id'], bool(hit)))
            used.update(hit)
        accepted = [(pathlib.PurePosixPath(e['file']).name, e['line']) for e in truth.get('accepted_extras', [])]
        traps = [(pathlib.PurePosixPath(d['file']).name, d['line']) for d in truth['decoys'] if d.get('kind') == 'preexisting']
        trap_hits = [i for i, b in enumerate(blocks) if any(abs(l - tl) <= 2 and f == tf for f, l in cites(b) for tf, tl in traps)]
        extra_idx = [i for i in range(len(blocks)) if i not in used]
        accepted_idx = [i for i in extra_idx if any(abs(l - al) <= a.window and f == af for f, l in cites(blocks[i]) for af, al in accepted)]
        tot['defects'] += len(truth['defects'])
        tot['found'] += sum(1 for _, ok in found if ok)
        tot['findings'] += len(blocks)
        tot['extras'] += len(extra_idx) - len(accepted_idx)
        tot['trap_hits'] += len(trap_hits)
        if not truth['defects']:
            tot['clean'] += 1
            clean_bad = [i for i in range(len(blocks)) if not any(abs(l - al) <= a.window and f == af for f, l in cites(blocks[i]) for af, al in accepted)]
            tot['clean_fp'] += len(clean_bad)
            tot['clean_ok'] += 1 if not clean_bad else 0
        print(f'{case:12} found {sum(1 for _, ok in found if ok)}/{len(truth["defects"])} '
              f'{",".join(i + ("+" if ok else "-") for i, ok in found):12} findings {len(blocks):2} extras {len(extra_idx) - len(accepted_idx):2} trap-hits {len(trap_hits)}')
    print('TOTAL', tot)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, fn in (('run', cmd_run), ('score', cmd_score)):
        p = sub.add_parser(name)
        p.add_argument('--arm', choices=['skills', 'baseline'], required=True)
        p.add_argument('--cases', default='all')
        p.add_argument('--workers', type=int, default=8)
        p.add_argument('--window', type=int, default=10)
        p.add_argument('--tag', default='', help='suffix for the results folder, for example -r2')
        p.add_argument('--agent-map', default='', help='axis=agent overrides, for example bug=defect-reviewer,simplicity=simplicity-reviewer')
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    sys.exit(main())
