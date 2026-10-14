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
# legacy branches on purpose: records written by older versions still carry these agent types
ALLOWED = {PLUGINS / 'agent-eval' / 'scripts' / 'subagent-usage-log.ps1', PLUGINS / 'agent-eval' / 'scripts' / 'subagent-usage-log.sh'}
# agents the guards and hooks are keyed on by name
GUARDED = ['browser-explorer', 'browser-operator', 'annotator', 'changelog-summarizer', 'verification-runner', 'code-explorer', 'contracts-reader']


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
    check('agents found', len(existing) >= 19, str(len(existing)))
    check('no removed agent file is still shipped', not (set(REMOVED) & existing), str(set(REMOVED) & existing))
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
    check('no file names a removed (merged) agent', not stale, ', '.join(stale[:8]))
    check("every subagent_type='...' in hooks, scripts and docs names an existing agent", not dangling, ', '.join(dangling[:8]))


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
