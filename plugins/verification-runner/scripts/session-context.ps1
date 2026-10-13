# SessionStart hook: stdout is injected into the session context.
try { Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot '../policy/runner.md') } catch { }
exit 0
