"""guard-agent-model (PreToolUse on the Agent tool): a main-agent call of the built-in general-purpose type is routed to haiku-delegation:coordinator (updatedInput, JSON checked here). Any other
subagent that is not a kit agent (Explore, Plan, no type) must be called with a Haiku model, and its brief must hold one unit of work (fewer than 4 numbered steps, at most 4000 characters). Kit agents
(haiku-pinned.txt) pin Haiku themselves and are never blocked. Only the main agent's calls are checked; bad input and the off switches (AGENT_MODEL_GUARD=off, AGENT_BRIEF_GUARD=off) allow the call;
AGENT_GENERAL_ROUTE=off turns the routing off. Runs the PowerShell and the POSIX sh version (whichever exist here) on the same inputs and requires the same exit code
and the same message. Run: python test_guard_agent_model.py"""
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capability import capability_variants, summary  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'haiku-delegation' / 'scripts'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    return capability_variants(SCRIPTS / 'guard-agent-model')


def hook(subagent, prompt='read the file and say what it does', model=None, agent_id=None):
    ti = {'description': 'x', 'prompt': prompt}
    if subagent is not None:
        ti['subagent_type'] = subagent
    if model is not None:
        ti['model'] = model
    d = {'hook_event_name': 'PreToolUse', 'tool_name': 'Agent', 'tool_input': ti}
    if agent_id:
        d['agent_id'] = agent_id
    return json.dumps(d)


def steps(n, text='do a thing'):
    return '\n'.join(f'{i}. {text}' for i in range(1, n + 1))


MODEL_MSG = 'would run on the main model'
UNITS_MSG = 'holds several units of work'
# label, stdin, env, wanted exit code, text the message must contain
ROUTED = ['haiku-delegation:coordinator', '"updatedInput"']   # sh keeps the input's spacing, ps1 writes compact JSON: the JSON check below compares the structure
CASES = [
    ('general-purpose without a model is routed to the kit coordinator', hook('general-purpose'), {}, 0, ROUTED),
    ('general-purpose on sonnet is routed too (routing does not depend on the model)', hook('general-purpose', model='sonnet'), {}, 0, ROUTED),
    ('general-purpose on opus is routed too', hook('general-purpose', model='opus'), {}, 0, ROUTED),
    ('general-purpose on haiku is routed too', hook('general-purpose', model='haiku'), {}, 0, ROUTED),
    ('a routed call skips the brief check (the coordinator splits the brief)', hook('general-purpose', prompt=steps(8)), {}, 0, ROUTED),
    ('no type and no model is blocked (it would be general-purpose)', hook(None), {}, 2, [MODEL_MSG, '(no type)']),
    ('no type on haiku is allowed', hook(None, model='haiku'), {}, 0, []),
    ('Explore without a model is blocked', hook('Explore'), {}, 2, [MODEL_MSG]),
    ('Plan on haiku is allowed', hook('Plan', model='haiku'), {}, 0, []),
    ('a kit agent with its plugin prefix needs no model', hook('haiku-delegation:code-explorer', prompt='Task kind: read\nq'), {}, 0, []),
    ('a kit agent by its bare name needs no model', hook('code-explorer', prompt='Task kind: read\nq'), {}, 0, []),
    ('the coordinator needs no model (pinned Haiku)', hook('haiku-delegation:coordinator', prompt=steps(8)), {}, 0, []),
    ('verification-runner needs no model', hook('verification-runner:verification-runner'), {}, 0, []),
    ('a kit agent may have a long brief with many numbered claims', hook('haiku-delegation:compliance-lister', prompt='Task kind: citation-verifier\n' + steps(30) + '\n' + 'x' * 5000), {}, 0, []),
    ('3 numbered steps are one brief', hook('Explore', model='haiku', prompt=steps(3)), {}, 0, []),
    ('4 numbered steps are several units', hook('Explore', model='haiku', prompt=steps(4)), {}, 2, [UNITS_MSG, '(4 numbered steps,', 'smallest piece of work that cannot be split any further']),
    ('numbered steps with a bracket and indent count too', hook('Explore', model='haiku', prompt='\n'.join(f'   {i}) step' for i in range(1, 6))), {}, 2, [UNITS_MSG]),
    ('a long single paragraph (4000 characters) is allowed', hook('Explore', model='haiku', prompt='x' * 4000), {}, 0, []),
    ('a longer brief (4001 characters) is several units', hook('Explore', model='haiku', prompt='x' * 4001), {}, 2, [UNITS_MSG, '4001 characters']),
    ('the model is checked before the brief size', hook('Explore', prompt=steps(6)), {}, 2, [MODEL_MSG]),
    ('AGENT_MODEL_GUARD=off allows a call without a model (and turns the routing off)', hook('general-purpose'), {'AGENT_MODEL_GUARD': 'off'}, 0, []),
    ('AGENT_GENERAL_ROUTE=off blocks general-purpose without a model', hook('general-purpose'), {'AGENT_GENERAL_ROUTE': 'off'}, 2, [MODEL_MSG, "'general-purpose'"]),
    ('AGENT_GENERAL_ROUTE=off lets general-purpose on haiku through', hook('general-purpose', model='haiku'), {'AGENT_GENERAL_ROUTE': 'off'}, 0, []),
    ('AGENT_BRIEF_GUARD=off allows a long brief', hook('Explore', model='haiku', prompt=steps(8)), {'AGENT_BRIEF_GUARD': 'off'}, 0, []),
    ('AGENT_BRIEF_GUARD=off does not allow a missing model', hook('Explore', prompt=steps(8)), {'AGENT_BRIEF_GUARD': 'off'}, 2, [MODEL_MSG]),
    ('a call made by a subagent (agent_id present) is not checked and not routed', hook('general-purpose', agent_id='abc123'), {}, 0, []),
    ('input that is not JSON is allowed (fail-open)', 'this is not json', {}, 0, []),
    ('empty input is allowed (fail-open)', '', {}, 0, []),
]


def run_all(jobs):
    """Runs the guard processes side by side (a shell guard under Git Bash is bound by process forks) and returns the results in order."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(lambda kw: subprocess.run(capture_output=True, text=True, timeout=120, **kw), jobs))


def main():
    ts = tools()
    check('at least one guard version can run here', bool(ts))
    jobs = [dict(args=cmd, input=stdin, env=dict(os.environ, **env)) for tool, cmd in ts.items() for label, stdin, env, want, texts in CASES]
    done = iter(run_all(jobs))
    seen = {}
    for tool, cmd in ts.items():
        seen[tool] = []
        for label, stdin, env, want, texts in CASES:
            p = next(done)
            seen[tool].append((p.returncode, p.stderr.strip()))
            check(f'[{tool}] {label}', p.returncode == want and all(t in p.stderr + p.stdout for t in texts), f'exit {p.returncode}, want {want}: {p.stderr[:200]} {p.stdout[:200]}')
    if len(ts) == 2:
        check('sh and ps1 return the same exit codes and the same messages', seen['sh'] == seen['ps1'], '\n'.join(f'{a} | {b}' for a, b in zip(seen['sh'], seen['ps1']) if a != b)[:600])
    # the routed call is one JSON object: the coordinator as subagent_type, the brief and the description kept unchanged
    brief = 'Find x.\nThen "y" and \\z.'
    routed = run_all([dict(args=cmd, input=hook('general-purpose', prompt=brief), env=dict(os.environ)) for cmd in ts.values()])
    for tool, p in zip(ts, routed):
        try:
            hso = json.loads(p.stdout)['hookSpecificOutput']
            ui = hso['updatedInput']
            # no permissionDecision: the routed call keeps the normal permission rules (the no-allow experiment ran without a prompt)
            ok = ui == {'description': 'x', 'prompt': brief, 'subagent_type': 'haiku-delegation:coordinator'} and 'permissionDecision' not in hso
        except (ValueError, KeyError, TypeError):
            ok = False
        check(f'[{tool}] the routed call is valid JSON with the brief and description kept', ok, p.stdout[:300])

    # haiku-pinned.txt agrees with the agent files
    pinned = [l.strip() for l in (SCRIPTS / 'haiku-pinned.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]
    agents = {}
    for p in (ROOT / 'plugins').glob('*/agents/*.md'):
        s = p.read_text(encoding='utf-8').replace('\r\n', '\n')
        agents[re.search(r'^name: (\S+)', s, re.M).group(1)] = re.search(r'^model: (\S+)', s, re.M)
    check('every agent in haiku-pinned.txt has an agent file', all(n in agents for n in pinned), str([n for n in pinned if n not in agents]))
    check('every kit agent file is listed in haiku-pinned.txt', sorted(agents) == sorted(pinned), str(sorted(set(agents) ^ set(pinned))))
    check('every pinned agent really pins a Haiku model in its own file', all(m and 'haiku' in m.group(1) for m in agents.values()), str([n for n, m in agents.items() if not (m and 'haiku' in m.group(1))]))
    hooks = json.loads((ROOT / 'plugins' / 'haiku-delegation' / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    pre = hooks['hooks'].get('PreToolUse', [])
    check('hooks.json registers guard-agent-model on the Agent tool through run.sh',
          any('Agent' in e.get('matcher', '') and any('guard-agent-model' in h['command'] and 'scripts/run.sh' in h['command'] for h in e['hooks']) for e in pre), str(pre))


main()
print(summary(results))
sys.exit(0 if all(results) else 1)
