"""Mark how a subagent run turned out.
Usage: python agent-usage-note.py <agent_id|last> ok|corrected|missed ["note"]
ok = the answer was right; corrected = you or the main model had to fix it; missed = it left something out.
Notes stay in the local log; keep them free of confidential content."""
import datetime as dt
import json
import pathlib
import sys

import os


def kit_data():
    d = os.environ.get('AGENT_KIT_DATA')
    if not d:
        c = os.environ.get('CLAUDE_CONFIG_DIR') or next((str(p.parent.parent) for p in pathlib.Path(__file__).resolve().parents if p.name == 'cache' and p.parent.name == 'plugins'), '') or str(pathlib.Path.home() / '.claude')
        d = str(pathlib.Path(c) / 'agent-kit')
    return pathlib.Path(d)


LOG = kit_data() / 'usage' / 'agent-usage.jsonl'
if len(sys.argv) < 3 or sys.argv[2] not in ('ok', 'corrected', 'missed'):
    sys.exit(__doc__)
runs = [json.loads(line) for line in LOG.read_text(encoding='utf-8-sig').splitlines() if '"type":"run"' in line]
agent_id = runs[-1]['agent_id'] if sys.argv[1] == 'last' else sys.argv[1]
if agent_id not in {r['agent_id'] for r in runs}:
    sys.exit('unknown agent_id: ' + agent_id)
rec = dict(schema='agent-usage/1', type='note', ts=dt.datetime.now(dt.timezone.utc).isoformat(), agent_id=agent_id,
           outcome=sys.argv[2], note=sys.argv[3] if len(sys.argv) > 3 else '')
with open(LOG, 'a', encoding='utf-8', newline='\n') as f:
    f.write(json.dumps(rec) + '\n')
print('recorded', agent_id, sys.argv[2])
