# SessionStart hook: stdout is injected into the session context.
Write-Output 'Machine shell: Windows PowerShell 5.1. Use PowerShell commands for host tasks; Bash (Git Bash) is also available. Kit scripts run as .ps1 here.'
try { Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot '../policy/guards.md') } catch { }
exit 0
