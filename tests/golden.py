"""Golden records for guard capabilities: the recorded behaviour of a capability is replayed through each implementation
that runs on this machine.

A record is a JSON list of cases. A case has
  id            name shown in the check line
  setup         {relpath: text | {text, age_days}}: files written under the case root before the first step
                  (age_days backdates the file's modification time)
  steps         list of runs in order (a stateful guard keeps its count between steps); each step has
                  write (optional {relpath: text | {text, age_days}}, written just before this step),
                  stdin (text), argv (list), env (dict), cwd (relpath, default '.'),
                  timeout (seconds, default 120; a hook that starts PowerShell may need more under load),
                  exit, stdout, stderr (expected)
  files         {relpath: text}: every file under the case root after the last step (a file the run wrote, or a setup file it kept)
  mask          optional [[regex, replacement], ...] applied (multi-line) to stdout, stderr and the file names and texts,
                after the placeholders are normalised: for values that differ from run to run (a backup's time stamp)
                or from machine to machine (the Versions line). A masked value is not checked by replay.
  setup values may also be {text, age_days, executable}: age_days backdates the file, executable sets its mode 0755 (a stub program)

Placeholders: {ROOT} stands for the case root. Each implementation receives the root in its own path form:
  sh   the Git Bash form on Windows (/c/Users/...), the native form elsewhere
  ps1  the Windows form (C:/Users/...)
{STUB_EXT} is '.cmd' for the PowerShell variant on Windows (a stub program there is a .cmd file), '' otherwise.
Recorded outputs and files store {ROOT}, so the same record holds for both forms.

record() runs each case through sh and ps1 (both must exist here), refuses to write unless they agree after normalising
{ROOT} and {TS} (every ISO-8601 'Z' time stamp), then writes the PowerShell result. replay() checks each implementation that
runs here against the record.

What is checked: exit codes, stdout and stderr after {ROOT} and {TS} are normalised, and the files a case leaves behind
(compared after CRLF is folded to LF). Each stdout and stderr stream also has its line endings checked: sh must write LF,
ps1 must write CRLF (the PowerShell console's line ending on Windows, kept on purpose). A stream that mixes the two fails.
Time stamps: only the value is masked ({TS} matches millisecond UTC stamps only), so a format difference shows as a difference.
What is not checked: the line endings of files a case leaves behind (the sh and ps1 writers differ there, and the record
holds one text per file).
"""
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

from capability import capability_variants

BASE = pathlib.Path.home() / '.agent-kit-golden'   # a long-name folder: the guards refuse 8.3 short names


def git_bash_path(p):
    s = pathlib.Path(p).as_posix()
    m = re.match(r'^([A-Za-z]):(.*)$', s)
    return f'/{m.group(1).lower()}{m.group(2)}' if m else s


def root_form(root, variant):
    if variant == 'sh' and os.name == 'nt':
        return git_bash_path(root)
    return pathlib.Path(root).as_posix()


def stub_ext(variant):
    return '.cmd' if variant == 'ps1' and os.name == 'nt' else ''


def fill(text, root, variant):
    if not isinstance(text, str):
        return text
    return text.replace('{ROOT}', root_form(root, variant)).replace('{STUB_EXT}', stub_ext(variant))


TS = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z')   # a run's own timestamp (millisecond UTC, the format sh and ps1 both write); only its value is masked, so a format drift shows as a difference


def normalise(text, root, variant):
    if not isinstance(text, str):
        return text
    return TS.sub('{TS}', text.replace(root_form(root, variant), '{ROOT}'))


def snapshot(root):
    """Every file under root, as {relpath: text}; binary files are skipped."""
    out = {}
    base = pathlib.Path(root)
    for f in sorted(base.rglob('*')):
        if f.is_file():
            try:
                out[f.relative_to(base).as_posix()] = f.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                pass
    return out


def write_file(root, rel, val, variant):
    d = val if isinstance(val, dict) else {'text': val}
    p = pathlib.Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fill(d['text'], root, variant), encoding='utf-8', newline='\n')
    if d.get('age_days') is not None:
        t = time.time() - d['age_days'] * 86400
        os.utime(p, (t, t))
    if d.get('executable'):
        p.chmod(0o755)


def apply_mask(text, masks):
    for pat, rep in masks:
        text = re.sub(pat, rep, text, flags=re.M)
    return text


# Line endings are part of the record, per implementation: sh writes LF, PowerShell's console writes CRLF on Windows (kept as it is).
EXPECTED_EOL = {'sh': 'lf', 'ps1': 'crlf'}


def universal(raw):
    """Content comparison: CRLF and a lone CR become LF (the same translation text mode applies)."""
    return raw.replace('\r\n', '\n').replace('\r', '\n')


def eol_style(raw):
    """'none' without a line break, 'lf' or 'crlf' when every break is that kind, 'mixed' otherwise."""
    lf = raw.count('\n')
    if lf == 0:
        return 'none'
    crlf = raw.count('\r\n')
    if crlf == lf:
        return 'crlf'
    return 'lf' if crlf == 0 else 'mixed'


def eol_ok(outcome, variant):
    return all(style in ('none', EXPECTED_EOL[variant])
               for step in outcome['steps'] for style in step.get('eol', {}).values())


def content(outcome):
    """What record() compares between sh and ps1: exit, stdout, stderr and files (line endings are checked on their own)."""
    return {'steps': [{k: s[k] for k in ('exit', 'stdout', 'stderr')} for s in outcome['steps']], 'files': outcome['files']}


def run_case(cmd, case, variant):
    """Runs one case in a fresh root and returns the normalised outcome of each step plus the files left behind."""
    BASE.mkdir(exist_ok=True)
    masks = case.get('mask', [])
    root = tempfile.mkdtemp(prefix='golden_', dir=BASE)
    try:
        for rel, val in case.get('setup', {}).items():
            write_file(root, rel, val, variant)
        steps = []
        for st in case['steps']:
            for rel, val in st.get('write', {}).items():
                write_file(root, rel, val, variant)
            env = dict(os.environ, **{k: fill(v, root, variant) for k, v in st.get('env', {}).items()})
            cwd = pathlib.Path(root) / st.get('cwd', '.')
            p = subprocess.run(cmd + [fill(a, root, variant) for a in st.get('argv', [])],
                               input=fill(st.get('stdin', ''), root, variant).encode('utf-8'), capture_output=True,
                               timeout=st.get('timeout', 120), env=env, cwd=str(cwd))
            out, err = p.stdout.decode('utf-8'), p.stderr.decode('utf-8')
            steps.append({'exit': p.returncode,
                          'stdout': apply_mask(normalise(universal(out), root, variant), masks),
                          'stderr': apply_mask(normalise(universal(err), root, variant), masks),
                          'eol': {'stdout': eol_style(out), 'stderr': eol_style(err)}})
        files = {apply_mask(rel, masks): apply_mask(normalise(text, root, variant), masks) for rel, text in snapshot(root).items()}
        return {'steps': steps, 'files': files}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_all(jobs):
    """(cmd, case, variant) jobs run side by side (a shell guard under Git Bash is bound by process forks)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(lambda job: run_case(job[0], job[1], job[2]), jobs))


def record(cases, script, path):
    """Returns the ids of cases where sh and ps1 disagree (the record is written only when there are none)."""
    ts = capability_variants(script)
    if set(ts) != {'sh', 'ps1'}:
        raise SystemExit(f'record needs both implementations here, have {sorted(ts)}')
    jobs = [(ts[v], c, v) for c in cases for v in ('sh', 'ps1')]
    done = iter(run_all(jobs))
    golden, bad = [], []
    for c in cases:
        out = {v: next(done) for v in ('sh', 'ps1')}
        if content(out['sh']) != content(out['ps1']) or not all(eol_ok(out[v], v) for v in out):
            bad.append(c['id'])
        golden.append({**c, 'steps': [{**st, 'exit': o['exit'], 'stdout': o['stdout'], 'stderr': o['stderr']}
                                      for st, o in zip(c['steps'], out['ps1']['steps'])],
                       'files': out['ps1']['files']})
    if not bad:
        pathlib.Path(path).parent.mkdir(exist_ok=True)
        pathlib.Path(path).write_text(json.dumps(golden, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return bad


def replay(path, script, results, check):
    """Checks every case of the record through each implementation here. check(name, ok, extra) is the suite's printer."""
    ts = capability_variants(script)
    check('at least one guard version can run here', bool(ts), '')
    cases = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    jobs = [(cmd, c, v) for v, cmd in ts.items() for c in cases]
    done = iter(run_all(jobs))
    for v in ts:
        for c in cases:
            got = next(done)
            wrong = []
            for i, (st, g) in enumerate(zip(c['steps'], got['steps'])):
                for f in ('exit', 'stdout', 'stderr'):
                    if g[f] != st[f]:
                        wrong.append(f'step {i + 1} {f}')
                for stream, style in g['eol'].items():
                    if style not in ('none', EXPECTED_EOL[v]):
                        wrong.append(f'step {i + 1} {stream} line endings {style} (expected {EXPECTED_EOL[v]})')
            if got['files'] != c.get('files', {}):
                wrong.append('files')
            check(f'[{v}] {c["id"]} matches the record', not wrong, 'differs in ' + ', '.join(wrong))
