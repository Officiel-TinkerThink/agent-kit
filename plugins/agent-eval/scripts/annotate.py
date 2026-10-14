"""Layer 2 write path. Validates one annotation JSON file (written by the `annotator` subagent into inbox/) and appends it to
annotations.jsonl. Append-only; the inbox file is kept as the original. Usage: python annotate.py --file <inbox/NAME.json>
Exit 0 = recorded, 2 = rejected (the reasons are printed so the annotator can fix the file and call again)."""
import datetime as dt
import hashlib
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


DATA_ROOT = kit_data()
USAGE_LOG = DATA_ROOT / 'usage' / 'agent-usage.jsonl'
START_LOG = pathlib.Path(os.environ['AGENT_START_LOG']) if os.environ.get('AGENT_START_LOG') else DATA_ROOT / 'usage' / 'agent-starts.jsonl'
ANN_LOG = DATA_ROOT / 'eval' / 'annotations.jsonl'
INBOX = DATA_ROOT / 'eval' / 'inbox'

OUTCOMES = {'wrong', 'partial', 'noncompliant', 'missed', 'disputed', 'ok'}
CODES = {'fabricated_fact', 'wrong_count', 'omission', 'wrong_line_citation', 'rule_violation', 'format_noncompliant',
         'verdict_given', 'secret_exposed', 'scope_creep', 'tool_misuse', 'misread_source', 'other'}
SEVERITY = {'low', 'medium', 'high'}
VERIFIED = {'yes', 'no', 'unclear'}
LIMITS = {'summary': 500, 'expected': 500, 'suggested_fix': 400, 'claim': 500}
SECRET_RE = re.compile(r'AKIA[0-9A-Z]{16}|squ_[0-9a-f]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9-]{10,}|'
                       r'-----BEGIN [A-Z ]*PRIVATE KEY-----|://[^/\s:@]+:[^@\s]{4,}@|(?i:password\s*[=:]\s*\S{6,})')


def runs():
    out = {}
    if USAGE_LOG.exists():
        for line in USAGE_LOG.read_text(encoding='utf-8-sig').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('type') == 'run':
                out[r['agent_id']] = r
    # a run the user stopped never reaches SubagentStop, so it has a start record (subagent-start-log) but no run record: it can still be annotated
    if START_LOG.exists():
        for line in START_LOG.read_text(encoding='utf-8-sig').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get('type') == 'start' and r.get('agent_id') and r['agent_id'] not in out:
                out[r['agent_id']] = {'type': 'start-only', 'agent_id': r['agent_id'], 'agent_type': r.get('agent_type') or 'unknown', 'effort': None}
    return out


def validate(a, known):
    errs = []
    need = ['run_agent_id', 'outcome', 'code', 'severity', 'summary', 'expected', 'evidence', 'verified', 'claim']
    for k in need:
        if k not in a:
            errs.append('missing field: ' + k)
    if errs:
        return errs
    rid = a['run_agent_id']
    if rid == 'last' or str(rid).startswith('last:'):
        errs.append('run_agent_id must be the real agent id, not "last" (look it up in <kit data>/usage/agent-usage.jsonl)')
    elif rid not in known:
        errs.append('unknown run_agent_id (not in <kit data>/usage/agent-usage.jsonl): %s' % rid)
    if a['outcome'] not in OUTCOMES:
        errs.append('outcome must be one of ' + ', '.join(sorted(OUTCOMES)))
    if a['code'] not in CODES:
        errs.append('code must be one of ' + ', '.join(sorted(CODES)))
    if a['severity'] not in SEVERITY:
        errs.append('severity must be one of low, medium, high')
    if a['verified'] not in VERIFIED:
        errs.append('verified must be yes, no or unclear')
    for k, n in LIMITS.items():
        v = a.get(k, '')
        if k in a and (not isinstance(v, str) or len(v) > n):
            errs.append('%s must be a string of at most %d characters' % (k, n))
    for k in ('summary', 'expected', 'claim'):
        if isinstance(a.get(k), str) and len(a[k].strip()) < 15:
            errs.append(k + ' is too short to be useful (at least 15 characters)')
    ev = a.get('evidence')
    if not isinstance(ev, list) or not (1 <= len(ev) <= 6):
        errs.append('evidence must be a list of 1 to 6 items')
    else:
        for i, e in enumerate(ev):
            if not isinstance(e, dict) or not isinstance(e.get('ref'), str) or not isinstance(e.get('note'), str) or not e['ref'] or len(e['note']) > 300:
                errs.append('evidence[%d] must be {"ref": "path:line or transcript ref", "note": "<=300 chars"}' % i)
    if a.get('outcome') == 'disputed' and a.get('verified') == 'yes':
        errs.append('outcome disputed means the claim could not be confirmed, so verified cannot be yes')
    if a.get('outcome') not in ('ok', 'disputed') and a.get('verified') == 'no':
        errs.append('verified no means the claim was not confirmed; use outcome disputed instead')
    blob = json.dumps(a)
    if SECRET_RE.search(blob):
        errs.append('the annotation contains something that looks like a secret or credential; describe it by location and kind only and never include the value')
    return errs


def main():
    if len(sys.argv) != 3 or sys.argv[1] != '--file':
        print(__doc__)
        return 2
    p = pathlib.Path(sys.argv[2]).resolve()
    try:
        p.relative_to(INBOX.resolve())
    except ValueError:
        print('REJECTED: the file must be inside ' + str(INBOX))
        return 2
    if not p.is_file():
        print('REJECTED: file not found')
        return 2
    raw = p.read_bytes()
    try:
        a = json.loads(raw.decode('utf-8-sig'))
    except ValueError as e:
        print('REJECTED: not valid JSON: %s' % e)
        return 2
    if not isinstance(a, dict):
        print('REJECTED: the file must contain one JSON object')
        return 2
    known = runs()
    errs = validate(a, known)
    if errs:
        print('REJECTED:\n- ' + '\n- '.join(errs))
        return 2
    run = known[a['run_agent_id']]
    ann_id = 'ann-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '-' + hashlib.sha256(raw).hexdigest()[:6]
    rec = {'schema': 'agent-annotation/1', 'type': 'annotation', 'annotation_id': ann_id,
           'ts': dt.datetime.now(dt.timezone.utc).isoformat(), 'run_agent_id': a['run_agent_id'], 'agent_type': run['agent_type'],
           'effort': run.get('effort'), 'run_record': run.get('type', 'run'), 'outcome': a['outcome'], 'code': a['code'], 'severity': a['severity'], 'summary': a['summary'].strip(),
           'expected': a['expected'].strip(), 'evidence': a['evidence'], 'suggested_fix': (a.get('suggested_fix') or '').strip(),
           'verified': a['verified'], 'claim': a['claim'].strip(), 'claimed_by': 'main-model', 'annotated_by': 'annotator-agent',
           'source_file': p.name, 'source_sha256': hashlib.sha256(raw).hexdigest()}
    ANN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ANN_LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print('RECORDED ' + ann_id)
    return 0


if __name__ == '__main__':
    sys.exit(main())
