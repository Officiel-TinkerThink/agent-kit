# agent-guards

Hooks, each scoped by agent type or tool; none changes your permission mode.

| Hook | Event | Effect |
|---|---|---|
| guard-secret-leak | PreToolUse `SubagentHandback`, `WebFetch`, `WebSearch` | redacts secret values from every subagent answer (known formats, key=value, URL credentials, CLI credentials, and any credential-looking value the agent itself read); blocks web calls containing them; audit holds kinds and counts only |
| guard-env-files | PreToolUse `Grep`, `Read` | `secret-candidate-lister`, `config-drift-checker` and `annotator` can never read real `.env` files |
| check-bulk-read | PreToolUse `Read`, `Bash` | whole-file reads above `BULK_READ_MIN_LINES` (default 200) in the main thread are redirected to `code-explorer` |
| guard-monitor-patterns | PreToolUse `Bash` | blocks foreground `tail -f`, `watch`, `Get-Content -Wait`, `logs -f`, unbounded `while true` |
| guard-git-readonly | PreToolUse `Bash` | `changelog-summarizer` may run one read-only git command only |
| guard-browser | PreToolUse `mcp__claude-in-chrome__*` | `browser-explorer` is read-only; `browser-operator` needs an `action_summary` per action, is blocked on irreversible effects, and is audited (an operator step whose audit record cannot be written is blocked, and the failure is traced in `hook-errors.log`); both limited to http(s) (+ optional host allowlist); the main thread is redirected to these agents (override `AGENT_KIT_BROWSER_MAIN=allow`) |

Two user commands ship with it (`skills/`). `/agent-guards:kit-allow` (only the user can start it) reviews the browser hosts the guard blocked (`audit/blocked-requests.jsonl`) and records the user's approval through `scripts/kit-policy`, appending the change with file hashes to `audit/policy-changes.jsonl`; it refuses to create a host list that would restrict browsing and never edits a malformed policy. Commands for `verification-runner` are not managed here: Claude Code's own permissions decide those. `/agent-guards:kit-doctor` (`scripts/kit-doctor`) is a read-only health check of the data folder, policy files, policy drift, hook errors and plugin versions.

Ships `changelog-summarizer` because it needs the git guard. Fails closed for subagent hand-back on an internal error; the cost-only guards fail open.
