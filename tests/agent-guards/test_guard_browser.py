"""Regression tests for guard-browser.ps1. Run: python test_guard_browser.py"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from capability import run_capability   # the OS adapter picks the implementation (PowerShell on Windows, sh on Linux)

HOOK = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'agent-guards' / 'scripts' / 'guard-browser.ps1'
P = 'mcp__claude-in-chrome__'
EXP, OPR = 'haiku-delegation:browser-explorer', 'haiku-delegation:browser-operator'


def case(name, agent, tool, ti, exp):
    return (name, {'agent_type': agent, 'session_id': 's1', 'tool_name': P + tool, 'tool_input': ti}, exp)


def click(summary=None, **kw):
    ti = {'action': 'left_click', 'coordinate': [1, 1], 'tabId': 1}
    if summary:
        ti['action_summary'] = summary
    ti.update(kw)
    return ti


CASES = [
    case('explorer: screenshot', EXP, 'computer', {'action': 'screenshot', 'tabId': 1}, 0),
    case('explorer: wait', EXP, 'computer', {'action': 'wait', 'duration': 3, 'tabId': 1}, 0),
    case('explorer: scroll', EXP, 'computer', {'action': 'scroll', 'tabId': 1}, 0),
    case('explorer: left_click blocked', EXP, 'computer', click(), 2),
    case('explorer: type blocked', EXP, 'computer', {'action': 'type', 'text': 'x', 'tabId': 1}, 2),
    case('explorer: key blocked', EXP, 'computer', {'action': 'key', 'text': 'Enter', 'tabId': 1}, 2),
    case('explorer: form_input blocked', EXP, 'form_input', {'ref': 'r', 'value': 'x', 'tabId': 1}, 2),
    case('explorer: javascript_tool blocked', EXP, 'javascript_tool', {'text': '1', 'tabId': 1}, 2),
    case('explorer: file_upload blocked', EXP, 'file_upload', {'tabId': 1}, 2),
    case('explorer: read_page', EXP, 'read_page', {'tabId': 1}, 0),
    case('explorer: navigate http', EXP, 'navigate', {'url': 'http://127.0.0.1:8765/x', 'tabId': 1}, 0),
    case('explorer: navigate bare host', EXP, 'navigate', {'url': 'example.com', 'tabId': 1}, 0),
    case('explorer: navigate back', EXP, 'navigate', {'url': 'back', 'tabId': 1}, 0),
    case('explorer: navigate file:', EXP, 'navigate', {'url': 'file:///C:/x', 'tabId': 1}, 2),
    case('explorer: navigate chrome://', EXP, 'navigate', {'url': 'chrome://settings', 'tabId': 1}, 2),
    case('explorer: navigate javascript:', EXP, 'navigate', {'url': 'javascript:alert(1)', 'tabId': 1}, 2),
    case('operator: click with benign summary', OPR, 'computer', click('Adds Widget to the cart'), 0),
    case('operator: click without summary', OPR, 'computer', click(), 2),
    case('operator: click delete', OPR, 'computer', click('Deletes the account'), 2),
    case('operator: click submit', OPR, 'computer', click('Submits the registration form'), 2),
    case('operator: click export', OPR, 'computer', click('Exports the CSV'), 2),
    case('operator: click send', OPR, 'computer', click('Sends the reply'), 2),
    case('operator: word boundary (designation ok)', OPR, 'computer', click('Opens the Designation tab'), 0),
    case('operator: form_input ok', OPR, 'form_input', {'ref': 'r', 'value': 'QA', 'action_summary': 'Sets Department to QA', 'tabId': 1}, 0),
    case('operator: form_input no summary', OPR, 'form_input', {'ref': 'r', 'value': 'QA', 'tabId': 1}, 2),
    case('operator: type ok', OPR, 'computer', {'action': 'type', 'text': 'Ada', 'action_summary': 'Types a name in the Name field', 'tabId': 1}, 0),
    case('operator: screenshot needs no summary', OPR, 'computer', {'action': 'screenshot', 'tabId': 1}, 0),
    case('operator: javascript_tool blocked', OPR, 'javascript_tool', {'text': '1', 'tabId': 1}, 2),
    case('operator: navigate data: blocked', OPR, 'navigate', {'url': 'data:text/html,hi', 'tabId': 1}, 2),
    case('other agent: unaffected', 'repo-scout', 'computer', click(), 0),
    case('main thread: chrome tool redirected', '', 'computer', click(), 2),
    case('main thread: navigate redirected', '', 'navigate', {'url': 'http://a.test', 'tabId': 1}, 2),
    case('main thread: tabs_context redirected', '', 'tabs_context_mcp', {}, 2),
    ('main thread: non-chrome tool unaffected', {'agent_type': '', 'tool_name': 'Read', 'tool_input': {'file_path': 'x'}}, 0),
    ('non-chrome tool: unaffected', {'agent_type': EXP, 'tool_name': 'Read', 'tool_input': {'file_path': 'x'}}, 0),
]


for _w in ['Removes the row', 'Pays the invoice', 'Purchases the plan', 'Buys the item', 'Approves the request', 'Signs the record', 'Confirms the order',
           'Publishes the page', 'Posts the comment', 'Transfers the funds', 'Discards the draft', 'Resets the password', 'Closes account', 'Cancels order', 'Cancels subscription']:
    CASES.append(case('operator: irreversible word -> ' + _w, OPR, 'computer', click(_w), 2))
for _u in ['chrome-extension://abc/x', 'view-source:http://a.test', 'about:blank', 'blob:http://a.test/1', 'ftp://a.test/f']:
    CASES.append(case('explorer: navigate scheme blocked ' + _u.split(':')[0], EXP, 'navigate', {'url': _u, 'tabId': 1}, 2))
for _a in ['right_click', 'double_click', 'triple_click', 'left_click_drag']:
    CASES.append(case('operator: ' + _a + ' needs summary', OPR, 'computer', {'action': _a, 'coordinate': [1, 1], 'tabId': 1}, 2))
for _a in ['scroll_to', 'zoom', 'hover']:
    CASES.append(case('explorer: ' + _a + ' allowed', EXP, 'computer', {'action': _a, 'tabId': 1}, 0))
for _t in ['tabs_context_mcp', 'tabs_create_mcp', 'tabs_close_mcp', 'get_page_text', 'find', 'read_console_messages', 'read_network_requests']:
    CASES.append(case('explorer: ' + _t + ' allowed', EXP, _t, {'tabId': 1}, 0))
CASES += [
    case('operator: key without summary', OPR, 'computer', {'action': 'key', 'text': 'Tab', 'tabId': 1}, 2),
    case('operator: key Tab with summary ok', OPR, 'computer', {'action': 'key', 'text': 'Tab', 'action_summary': 'Moves focus to the next field', 'tabId': 1}, 0),
    case('operator: key Enter blocked', OPR, 'computer', {'action': 'key', 'text': 'Enter', 'action_summary': 'Moves to the next step', 'tabId': 1}, 2),
    case('operator: key ctrl+Return blocked', OPR, 'computer', {'action': 'key', 'text': 'ctrl+Return', 'action_summary': 'Applies the filter', 'tabId': 1}, 2),
    case('operator: whitespace-only summary', OPR, 'computer', click('   '), 2),
    case('explorer: unparseable url', EXP, 'navigate', {'url': 'http://[bad', 'tabId': 1}, 2),
    case('bare agent name browser-explorer is guarded', 'browser-explorer', 'computer', click(), 2),
    case('bare agent name browser-operator is guarded', 'browser-operator', 'computer', click(), 2),
]


def run(env, payload):
    p = run_capability(HOOK, input=payload, capture_output=True, text=True, env=env)
    return p.returncode


def main():
    kit = tempfile.mkdtemp(prefix='kitdata-')
    env = dict(os.environ, AGENT_KIT_DATA=kit)
    bad = ok = 0

    def report(name, passed, extra=''):
        nonlocal ok, bad
        print(('PASS' if passed else 'FAIL'), name, extra)
        ok += bool(passed)
        bad += not passed

    for name, payload, exp in CASES:
        got = run(env, json.dumps(payload))
        report(name, got == exp, '' if got == exp else f'(expected {exp}, got {got})')
    pathlib.Path(kit, 'browser-policy.json').write_text(json.dumps({'allowedHosts': ['127.0.0.1', 'docs.example.com']}))
    for name, url, exp in [('policy: allowed host', 'http://127.0.0.1:8765/a', 0), ('policy: allowed host 2', 'https://docs.example.com/x', 0),
                           ('policy: other host blocked', 'https://evil.test/', 2)]:
        got = run(env, json.dumps({'agent_type': EXP, 'tool_name': P + 'navigate', 'tool_input': {'url': url, 'tabId': 1}}))
        report(name, got == exp)
    run(env, json.dumps({'agent_type': OPR, 'session_id': 's9', 'tool_name': P + 'computer',
                         'tool_input': {'action': 'type', 'text': 'SECRET-TEXT', 'action_summary': 'Types a name', 'tabId': 1}}))
    log = pathlib.Path(kit, 'audit', 'browser-actions.jsonl')
    text = log.read_text(encoding='utf-8-sig') if log.exists() else ''
    report('audit: file written', bool(text))
    report('audit: typed text not logged', 'SECRET-TEXT' not in text)
    report('audit: text length logged', '"text_len":11' in text)
    pathlib.Path(kit, 'browser-policy.json').write_text(json.dumps({'allowedHosts': []}))
    got = run(env, json.dumps({'agent_type': EXP, 'tool_name': P + 'navigate', 'tool_input': {'url': 'https://any.test/', 'tabId': 1}}))
    report('policy: empty allowedHosts allows all', got == 0)
    pathlib.Path(kit, 'browser-policy.json').write_text('{not json')
    got = run(env, json.dumps({'agent_type': EXP, 'tool_name': P + 'navigate', 'tool_input': {'url': 'https://any.test/', 'tabId': 1}}))
    report('internal error fails closed for guarded agent', got == 2)
    got = run(env, json.dumps({'agent_type': 'repo-scout', 'tool_name': P + 'navigate', 'tool_input': {'url': 'https://any.test/', 'tabId': 1}}))
    report('internal error: other agents unaffected', got == 0)
    pathlib.Path(kit, 'browser-policy.json').unlink()
    got = run(dict(env, AGENT_KIT_BROWSER_MAIN='allow'), json.dumps({'agent_type': '', 'tool_name': P + 'navigate', 'tool_input': {'url': 'http://a.test', 'tabId': 1}}))
    report('main thread: AGENT_KIT_BROWSER_MAIN=allow overrides', got == 0)
    got = run(env, 'this is not json')
    report('garbage input fails open', got == 0)
    run(env, json.dumps({'agent_type': OPR, 'session_id': 's10', 'tool_name': P + 'computer', 'tool_input': click('Deletes the account')}))
    report('audit: blocked decision recorded', '"decision":"blocked"' in log.read_text(encoding='utf-8-sig'))
    # audit trail unwritable: <KIT_DATA>/audit is a FILE, so the operator is not allowed to act (no record, no action)
    bad_kit = tempfile.mkdtemp(prefix='kitdata-bad-')
    pathlib.Path(bad_kit, 'audit').write_text('not a directory')
    bad_env = dict(os.environ, AGENT_KIT_DATA=bad_kit)
    op_click = json.dumps({'agent_type': OPR, 'session_id': 's11', 'tool_name': P + 'computer', 'tool_input': click('Adds Widget to the cart')})
    report('audit unwritable: operator action blocked', run(bad_env, op_click) == 2)
    report('audit unwritable: failure traced in hook-errors.log',
           'audit write failed' in pathlib.Path(bad_kit, 'hook-errors.log').read_text(encoding='utf-8-sig') if pathlib.Path(bad_kit, 'hook-errors.log').exists() else False)
    report('audit unwritable: explorer read still allowed',
           run(bad_env, json.dumps({'agent_type': EXP, 'tool_name': P + 'read_page', 'tool_input': {'tabId': 1}})) == 0)
    report('audit unwritable: blocked step still blocked', run(bad_env, json.dumps({'agent_type': OPR, 'tool_name': P + 'computer', 'tool_input': click('Deletes the account')})) == 2)

    # KIT_DATA resolved from the plugin cache path when CLAUDE_CONFIG_DIR and AGENT_KIT_DATA are both unset
    cfg = pathlib.Path(tempfile.mkdtemp(prefix='cfgdir-'))
    cached = cfg / 'plugins' / 'cache' / 'agent-kit' / 'agent-guards' / '0.0.0' / 'scripts'
    cached.mkdir(parents=True)
    copy = cached / HOOK.name
    copy.write_bytes(HOOK.read_bytes())
    for sib in (HOOK.with_suffix('.sh'), HOOK.parent / 'lib.sh', HOOK.parent / 'run.sh'):   # the adapter, the shell version and its helper travel with the script
        if sib.exists():
            (cached / sib.name).write_bytes(sib.read_bytes())
    home = tempfile.mkdtemp(prefix='home-')
    env2 = {k: v for k, v in os.environ.items() if k not in ('AGENT_KIT_DATA', 'CLAUDE_CONFIG_DIR')}
    env2['USERPROFILE'] = home
    env2['HOME'] = home
    run_capability(copy, input=op_click, capture_output=True, text=True, env=env2)
    report('KIT_DATA derived from plugin cache path (no env)', (cfg / 'agent-kit' / 'audit' / 'browser-actions.jsonl').exists())
    report('KIT_DATA derivation did not touch USERPROFILE\\.claude', not pathlib.Path(home, '.claude').exists())

    print(f'\n{ok}/{ok + bad} passed')
    sys.exit(1 if bad else 0)


main()
