"""No hook, script, policy or doc may name an agent that does not exist. A hook that tells the main agent to call `subagent_type='x'` for an agent that was merged or renamed
would send every redirect to nothing. Also: the agents that guards are keyed on must exist. Run: python test_agent_references.py"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGINS = ROOT / 'plugins'
results = []

# agents merged into code-explorer and contracts-reader in 0.2.0; their names must not appear in anything a user or agent reads
REMOVED = ['repo-scout', 'bulk-reader', 'module-mapper', 'inventory-extractor', 'test-case-lister',
           'schema-reader', 'contract-reader', 'migration-checker', 'api-contract-checker']
# agents merged in the topic merge that followed: their names live on as kinds (`Task kind: log-triage`), so the names may appear in text,
# but no agent file may exist under them and no subagent_type may name them
MERGED_INTO_KINDS = ['pipeline-reader', 'dependency-reader', 'config-drift-checker', 'spec-extractor', 'doc-link-checker', 'doc-drafter',
                     'log-triage', 'test-run-summarizer', 'ticket-classifier', 'audit-coverage-lister', 'secret-candidate-lister', 'citation-verifier',
                     'doc-researcher', 'release-diff', 'advisory-collector']
# legacy branches on purpose: records written by older versions still carry these agent types
ALLOWED = {PLUGINS / 'agent-eval' / 'scripts' / 'subagent-usage-log.ps1', PLUGINS / 'agent-eval' / 'scripts' / 'subagent-usage-log.sh'}
# agents the guards and hooks are keyed on by name
GUARDED = ['browser-explorer', 'browser-operator', 'annotator', 'changelog-summarizer', 'verification-runner', 'code-explorer', 'contracts-reader', 'infra-reader', 'docs-reader', 'triage', 'compliance-lister', 'researcher']


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def scanned():
    files = []
    for pat in ('*/scripts/*', '*/hooks/*', '*/policy/*', '*/skills/*/SKILL.md', '*/templates/*', '*/README.md', '*/agents/*.md'):
        files += [f for f in PLUGINS.glob(pat) if f.is_file() and f.suffix in ('.sh', '.ps1', '.json', '.md', '.py', '')]
    files += [ROOT / n for n in ('README.md', 'SUBAGENTS.md', 'CONTRIBUTING.md', 'CLAUDE.md')]
    return [f for f in files if f.exists() and f not in ALLOWED and '__pycache__' not in f.parts]


def main():
    existing = {f.stem for f in PLUGINS.glob('*/agents/*.md')}
    check('agents found', len(existing) >= 9, str(len(existing)))
    check('no removed agent file is still shipped', not ((set(REMOVED) | set(MERGED_INTO_KINDS)) & existing), str((set(REMOVED) | set(MERGED_INTO_KINDS)) & existing))
    for name in GUARDED:
        check(f'guarded agent exists: {name}', name in existing)
    files = scanned()
    check('files scanned', len(files) >= 40, str(len(files)))
    pat = re.compile(r'(?<![\w-])(' + '|'.join(map(re.escape, REMOVED)) + r')(?![\w-])')
    stale = []
    dangling = []
    for f in files:
        text = f.read_text(encoding='utf-8', errors='replace')
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                stale.append(f'{f.relative_to(ROOT).as_posix()}:{i}')
            for m in re.finditer(r"subagent_type\s*=\s*['\"]([\w:-]+)['\"]", line):
                if m.group(1).split(':')[-1] not in existing:
                    dangling.append(f'{f.relative_to(ROOT).as_posix()}:{i} -> {m.group(1)}')
    # plugin agents only resolve under their full name <plugin>:<agent>; no text may say the prefix is optional, and the session policy lists every agent's prefix
    optional = [f.relative_to(ROOT).as_posix() for f in files if re.search(r'prefix is optional|plain name also works', f.read_text(encoding='utf-8', errors='replace'))]
    check('no text claims that the plugin prefix of an agent name is optional', not optional, ', '.join(optional))
    policy = (PLUGINS / 'haiku-delegation' / 'policy' / 'haiku-delegation.md').read_text(encoding='utf-8')
    full = next((l for l in policy.splitlines() if l.startswith('Full names:')), '')
    check('the session policy tells the main agent to use the full <plugin>:<agent> name', 'FULL name' in policy and bool(full))
    missing = [f'{p.parent.parent.name}:{p.stem}' for p in PLUGINS.glob('*/agents/*.md')
               if p.stem not in full or (f'`{p.parent.parent.name}:`' not in full and f'`{p.parent.parent.name}:{p.stem}`' not in full)]
    check('the "Full names" line of the session policy lists every agent under its plugin prefix', not missing, ', '.join(missing))
    # every kit agent knows it is one unit of work and what to do with a brief that holds several
    # the coordinator is the one agent that takes multi-unit briefs on purpose: it decomposes them itself, so it is exempt
    no_unit = [p.stem for p in PLUGINS.glob('*/agents/*.md') if p.stem != 'coordinator' and ('- One unit: your brief is one unit of work' not in p.read_text(encoding='utf-8') or 'NOT DONE (send each to its own agent)' not in p.read_text(encoding='utf-8'))]
    check('every agent file has the "One unit" rule (a brief with several questions: do the first, list the rest as NOT DONE)', not no_unit, ', '.join(no_unit))
    check('no file names a removed (merged) agent', not stale, ', '.join(stale[:8]))
    check("every subagent_type='...' in hooks, scripts and docs names an existing agent", not dangling, ', '.join(dangling[:8]))


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
