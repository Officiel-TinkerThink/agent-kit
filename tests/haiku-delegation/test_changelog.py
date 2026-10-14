"""CHANGELOG.md must exist, keep an [Unreleased] section, and have an entry for the version every plugin and the marketplace carry.
Run: python test_changelog.py"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
results = []


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    log = ROOT / 'CHANGELOG.md'
    check('CHANGELOG.md exists', log.is_file())
    if not log.is_file():
        return
    text = log.read_text(encoding='utf-8')
    versions = {}
    for p in sorted((ROOT / 'plugins').glob('*/.claude-plugin/plugin.json')):
        versions[p.parent.parent.name] = json.loads(p.read_text(encoding='utf-8'))['version']
    market = json.loads((ROOT / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
    for entry in market['plugins']:
        versions['marketplace:' + entry['name']] = entry['version']
    check('plugins and marketplace entries exist', len(versions) >= 8, str(versions))
    check('all plugins and the marketplace carry one version', len(set(versions.values())) == 1, str(versions))
    version = next(iter(set(versions.values())))
    check('has an [Unreleased] section', re.search(r'(?m)^## \[Unreleased\]\s*$', text) is not None)
    check(f'has a dated entry for the current version {version}', re.search(r'(?m)^## \[' + re.escape(version) + r'\] - \d{4}-\d{2}-\d{2}\s*$', text) is not None)
    heads = re.findall(r'(?m)^## \[(\d+\.\d+\.\d+)\]', text)
    key = lambda v: tuple(int(x) for x in v.split('.'))
    check('released versions are listed newest first, once each', heads == sorted(set(heads), key=key, reverse=True), str(heads))
    check('no released version is newer than the one the plugins carry', all(key(v) <= key(version) for v in heads), str(heads))


main()
print(f'{sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
