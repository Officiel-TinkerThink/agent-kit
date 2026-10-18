# PreToolUse hook (PowerShell and Bash), registered by the agent-guards plugin. Windows version: PowerShell is this
# machine's shell, so nothing here needs blocking. The file exists so run.sh finds it and does not block every call.
# The POSIX version (guard-shell-os.sh) is the one that blocks, on machines without Windows PowerShell.
exit 0
