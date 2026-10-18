"""Run a kit capability through the OS adapter (plugins/<plugin>/scripts/run.sh).

Tests never name PowerShell or a shell version. run.sh picks the implementation for the machine:
Windows runs the .ps1 in Windows PowerShell 5.1, Linux and WSL run the .sh. See docs/design/shell-adapter.md.
A test that copies a capability to a temporary folder must copy both twins, or the adapter cannot route it.
"""
import os
import pathlib
import shutil
import subprocess

SH = shutil.which('sh')


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
