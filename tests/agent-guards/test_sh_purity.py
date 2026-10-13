"""The Linux scripts (plugins/*/scripts/*.sh) must be pure POSIX sh: no PowerShell, Python, jq or perl, no bash-only syntax,
valid syntax under dash (Ubuntu's /bin/sh) when it is installed. Run: python test_sh_purity.py"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = sorted((ROOT / 'plugins').glob('*/scripts/*.sh'))
DASH = shutil.which('dash')
results = []

# (pattern, why). Matched per line on code only (comment lines and text inside awk/sed programs may legitimately mention words).
FORBIDDEN_COMMANDS = re.compile(r'(^|[;&|(`]|\$\(|\bthen\b|\bdo\b|\belse\b)\s*(python3?|pwsh|powershell(\.exe)?|jq|perl|ruby|node)\b')
BASHISMS = [
    (re.compile(r'\[\[ '), '[[ ]]'),
    (re.compile(r'\becho\s+-e\b'), 'echo -e'),
    (re.compile(r"(?<![\"'])\$'[^']*'"), "$'...'"),
    (re.compile(r'<\('), 'process substitution'),
    (re.compile(r'\$\{[A-Za-z_][A-Za-z0-9_]*//'), '${var//x/y}'),
    (re.compile(r'\$\{[A-Za-z_][A-Za-z0-9_]*(,,|\^\^)\}'), 'case modification'),
    (re.compile(r'^\s*local\s'), 'local'),
    (re.compile(r'^\s*(declare|typeset|shopt|mapfile|readarray)\s'), 'bash builtin'),
    (re.compile(r'^\s*source\s+\S'), 'source (use .)'),
    (re.compile(r'[A-Za-z_]+=\('), 'array'),
]


def check(name, ok, extra=''):
    results.append(bool(ok))
    print(('PASS' if ok else 'FAIL'), name, '' if ok else extra)


def main():
    check('shell scripts found', len(SCRIPTS) >= 20, str(len(SCRIPTS)))
    for f in SCRIPTS:
        rel = f.relative_to(ROOT).as_posix()
        raw = f.read_bytes()
        text = raw.decode('utf-8')
        check(f'{rel}: LF endings, no BOM', b'\r' not in raw and not raw.startswith(b'\xef\xbb\xbf'))
        lines = text.split('\n')
        bad = []
        for n, line in enumerate(lines, 1):
            code = line.strip()
            if not code or code.startswith('#'):
                continue
            if FORBIDDEN_COMMANDS.search(code):
                bad.append(f'{n}: runs a non-sh interpreter: {code[:80]}')
            for rx, why in BASHISMS:
                if rx.search(code):
                    bad.append(f'{n}: {why}: {code[:80]}')
        check(f'{rel}: no other interpreter, no bashisms', not bad, '; '.join(bad[:3]))
        if f.name != 'run.sh' and f.name != 'lib.sh':
            check(f'{rel}: has a PowerShell twin', f.with_suffix('.ps1').exists())
        if DASH:
            p = subprocess.run([DASH, '-n', str(f)], capture_output=True, text=True)
            check(f'{rel}: dash -n syntax', p.returncode == 0, p.stderr[:200])
    print(f'\n{sum(results)}/{len(results)} passed' + ('' if DASH else '  (dash not installed: syntax check skipped)'))
    sys.exit(0 if all(results) else 1)


main()
