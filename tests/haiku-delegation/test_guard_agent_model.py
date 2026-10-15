"""guard-agent-model (PreToolUse on the Agent tool): a subagent that is not a kit agent (general-purpose, Explore, Plan, no type) must be called with a Haiku model, and its brief must hold one unit
of work (fewer than 4 numbered steps, at most 4000 characters). Kit agents (haiku-pinned.txt) pin Haiku themselves and are never blocked. Only the main agent's calls are checked; bad input and the
off switches (AGENT_MODEL_GUARD=off, AGENT_BRIEF_GUARD=off) allow the call. Runs the PowerShell and the POSIX sh version (whichever exist here) on the same inputs and requires the same exit code
and the same message. Run: python test_guard_agent_model.py"""
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'plugins' / 'haiku-delegation' / 'scripts'
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def tools():
    out = {}
    if shutil.which('sh'):
        out['sh'] = ['sh', str(SCRIPTS / 'guard-agent-model.sh')]
    ps = (shutil.which('powershell.exe') or shutil.which('powershell')) if sys.platform == 'win32' else shutil.which('pwsh')   # not the Windows powershell.exe that WSL exposes through interop
    if ps:
        out['ps1'] = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / 'guard-agent-model.ps1')]
    return out


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
CASES = [
    ('general-purpose without a model is blocked', hook('general-purpose'), {}, 2, [MODEL_MSG, 'model: "haiku"', "'general-purpose'"]),
    ('general-purpose on sonnet is blocked', hook('general-purpose', model='sonnet'), {}, 2, [MODEL_MSG]),
    ('general-purpose on opus is blocked', hook('general-purpose', model='opus'), {}, 2, [MODEL_MSG]),
    ('general-purpose on haiku is allowed', hook('general-purpose', model='haiku'), {}, 0, []),
    ('a full Haiku model id is allowed', hook('general-purpose', model='claude-haiku-5-5'), {}, 0, []),
    ('HAIKU in capitals is allowed', hook('general-purpose', model='HAIKU'), {}, 0, []),
    ('no type and no model is blocked (it would be general-purpose)', hook(None), {}, 2, [MODEL_MSG, '(no type)']),
    ('no type on haiku is allowed', hook(None, model='haiku'), {}, 0, []),
    ('Explore without a model is blocked', hook('Explore'), {}, 2, [MODEL_MSG]),
    ('Plan on haiku is allowed', hook('Plan', model='haiku'), {}, 0, []),
    ('a kit agent with its plugin prefix needs no model', hook('haiku-delegation:code-explorer', prompt='Task kind: read\nq'), {}, 0, []),
    ('a kit agent by its bare name needs no model', hook('code-explorer', prompt='Task kind: read\nq'), {}, 0, []),
    ('verification-runner needs no model', hook('verification-runner:verification-runner'), {}, 0, []),
    ('a kit agent may have a long brief with many numbered claims', hook('haiku-delegation:compliance-lister', prompt='Task kind: citation-verifier\n' + steps(30) + '\n' + 'x' * 5000), {}, 0, []),
    ('3 numbered steps are one brief', hook('general-purpose', model='haiku', prompt=steps(3)), {}, 0, []),
    ('4 numbered steps are several units', hook('general-purpose', model='haiku', prompt=steps(4)), {}, 2, [UNITS_MSG, '(4 numbered steps,', 'smallest piece of work that cannot be split any further']),
    ('numbered steps with a bracket and indent count too', hook('general-purpose', model='haiku', prompt='\n'.join(f'   {i}) step' for i in range(1, 6))), {}, 2, [UNITS_MSG]),
    ('a long single paragraph (4000 characters) is allowed', hook('general-purpose', model='haiku', prompt='x' * 4000), {}, 0, []),
    ('a longer brief (4001 characters) is several units', hook('general-purpose', model='haiku', prompt='x' * 4001), {}, 2, [UNITS_MSG, '4001 characters']),
    ('the model is checked before the brief size', hook('general-purpose', prompt=steps(6)), {}, 2, [MODEL_MSG]),
    ('AGENT_MODEL_GUARD=off allows a call without a model', hook('general-purpose'), {'AGENT_MODEL_GUARD': 'off'}, 0, []),
    ('AGENT_BRIEF_GUARD=off allows a long brief', hook('general-purpose', model='haiku', prompt=steps(8)), {'AGENT_BRIEF_GUARD': 'off'}, 0, []),
    ('AGENT_BRIEF_GUARD=off does not allow a missing model', hook('general-purpose', prompt=steps(8)), {'AGENT_BRIEF_GUARD': 'off'}, 2, [MODEL_MSG]),
    ('a call made by a subagent (agent_id present) is not checked', hook('general-purpose', agent_id='abc123'), {}, 0, []),
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
            check(f'[{tool}] {label}', p.returncode == want and all(t in p.stderr for t in texts), f'exit {p.returncode}, want {want}: {p.stderr[:200]}')
    if len(ts) == 2:
        check('sh and ps1 return the same exit codes and the same messages', seen['sh'] == seen['ps1'], '\n'.join(f'{a} | {b}' for a, b in zip(seen['sh'], seen['ps1']) if a != b)[:600])

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
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
