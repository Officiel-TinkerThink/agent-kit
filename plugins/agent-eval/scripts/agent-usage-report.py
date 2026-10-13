"""Summarise <kit data>/usage/agent-usage.jsonl per agent type and effort.
Usage: python agent-usage-report.py [--days N] [--agent NAME]
Costs are ESTIMATES (Haiku 5.5 list price; cache read 10% / write 125% assumed).
The ok / corr / miss columns come from agent-usage-note.py (latest mark per run)."""
import collections
import datetime as dt
import json
import pathlib
import re
import sys

import os


def kit_data():
    d = os.environ.get('AGENT_KIT_DATA')
    if not d:
        c = os.environ.get('CLAUDE_CONFIG_DIR') or next((str(p.parent.parent) for p in pathlib.Path(__file__).resolve().parents if p.name == 'cache' and p.parent.name == 'plugins'), '') or str(pathlib.Path.home() / '.claude')
        d = str(pathlib.Path(c) / 'agent-kit')
    return pathlib.Path(d)


LOG = kit_data() / 'usage' / 'agent-usage.jsonl'


def parse_ts(s):
    # the hook writes 7 fractional digits and a Z suffix; Python 3.10 accepts neither
    s = re.sub(r'(\.\d{6})\d+', r'\1', s).replace('Z', '+00:00')
    return dt.datetime.fromisoformat(s)


args = sys.argv[1:]
days = int(args[args.index('--days') + 1]) if '--days' in args else None
only = args[args.index('--agent') + 1] if '--agent' in args else None
if not LOG.exists():
    sys.exit('no log yet: ' + str(LOG))
cut = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days) if days else None
runs, notes = {}, collections.defaultdict(list)
for line in LOG.read_text(encoding='utf-8-sig').splitlines():
    try:
        r = json.loads(line)
    except ValueError:
        continue
    if r.get('type') == 'run':
        if cut and parse_ts(r['ts']) < cut:
            continue
        if only and r['agent_type'] != only:
            continue
        runs[r['agent_id']] = r
    elif r.get('type') == 'note':
        notes[r['agent_id']].append(r)
groups = collections.defaultdict(list)
for r in runs.values():
    groups[(r['agent_type'], r.get('effort') or '-')].append(r)
print(f"{'agent':24}{'effort':8}{'runs':>5}{'avg s':>7}{'avg out tok':>12}{'avg calls':>10}{'avg est $':>10}{'ok':>4}{'corr':>5}{'miss':>5}")
for (agent, effort), rs in sorted(groups.items()):
    n = len(rs)
    outcomes = collections.Counter(notes[r['agent_id']][-1]['outcome'] for r in rs if notes.get(r['agent_id']))

    def avg(f):
        return sum(f(r) or 0 for r in rs) / n

    print(f"{agent:24}{effort:8}{n:5}{avg(lambda r: r['duration_s']):7.0f}{avg(lambda r: r['tokens']['output']):12.0f}"
          f"{avg(lambda r: r['api_calls']):10.1f}{avg(lambda r: r['est_cost_usd']):10.4f}"
          f"{outcomes['ok']:4}{outcomes['corrected']:5}{outcomes['missed']:5}")
marked = sum(1 for aid in runs if notes.get(aid))
print(f"\n{len(runs)} runs, {marked} marked. Newest agent ids: " + ', '.join(list(runs)[-3:]))
