"""Run a kit capability through the OS adapter (plugins/<plugin>/scripts/run.sh).

Tests never name PowerShell or a shell version. run.sh picks the implementation for the machine:
Windows runs the .ps1 in Windows PowerShell 5.1, Linux and WSL run the .sh. See docs/design/shell-adapter.md.
A test that copies a capability to a temporary folder must copy both twins, or the adapter cannot route it.
"""
import os
import pathlib
import shutil
import subprocess
import sys

SH = shutil.which('sh')
POWERSHELL = shutil.which('powershell.exe') if sys.platform == 'win32' else None
# Implementations this machine cannot run, as 'name: reason'. Filled by capability_variants(), printed by summary().
NOT_APPLICABLE = []


def capability_variants(script):
    """The runnable implementations of one capability, keyed like the adapter: {'sh': [...], 'ps1': [...]}.
    script: the capability's path, with or without a .sh or .ps1 suffix. Linux runs only sh (no PowerShell there, by design).
    A missing implementation is recorded in NOT_APPLICABLE and printed by summary(), never dropped silently."""
    script = pathlib.Path(script)
    name = script.with_suffix('')
    out = {}
    if SH:
        out['sh'] = [SH, str(name) + '.sh']
    else:
        NOT_APPLICABLE.append('sh: no POSIX sh on this machine')
    if POWERSHELL:
        out['ps1'] = [POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(name) + '.ps1']
    elif 'ps1: no Windows PowerShell on this machine' not in NOT_APPLICABLE:
        NOT_APPLICABLE.append('ps1: no Windows PowerShell on this machine')
    return out


def summary(results):
    """The suite's final line: 'N/M passed', plus 'K not applicable: <reasons>' when a variant could not run here."""
    line = f'{sum(results)}/{len(results)} passed'
    if NOT_APPLICABLE:
        line += f', {len(NOT_APPLICABLE)} not applicable: ' + '; '.join(NOT_APPLICABLE)
    return line


def run_capability(script, *args, **kwargs):
    """script: the capability's path, with or without a .ps1 or .sh suffix. args are passed to the script.
    kwargs go to subprocess.run (input, capture_output, text, env, timeout)."""
    script = pathlib.Path(script)
    adapter = script.parent / 'run.sh'
    name = script.with_suffix('')
    # Git Bash expands wildcards in the argument list of sh.exe itself, before run.sh runs, so a path like app/*/f.txt
    # reaches the guard as a list of real files. MSYS=noglob stops that. It is ignored on Linux.
    env = dict(kwargs.pop('env', None) or os.environ)
    env['MSYS'] = 'noglob'
    return subprocess.run([SH, adapter.as_posix(), name.as_posix(), *map(str, args)], env=env, **kwargs)
