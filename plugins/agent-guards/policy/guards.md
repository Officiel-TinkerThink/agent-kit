# Guard hooks (agent-guards plugin)

Waiting and monitoring (every poll is a turn that re-bills the whole context, so never poll or stream into the conversation; a hook blocks foreground `tail -f`, `watch` and unbounded `while true`):
- One event ("tell me when X is ready"): Bash with run_in_background and a command that exits when the condition is true, e.g. `until grep -q READY app.log; do sleep 1; done`. You get one notification.
- One notification per occurrence: the Monitor tool with a filtered stream, e.g. `tail -f app.log | grep --line-buffered -E 'ERROR|Traceback|FAILED|READY'`. The filter must cover failure states, not only success, because silence looks identical to "still running".
- Otherwise a bounded check that prints a few lines and exits (`tail -n 20`, a count, the changed fields only).

Secrets: a hook redacts secret-looking values (known token formats, URL passwords, key=value, CLI credentials, and any value the agent itself read that looks like a credential) from every subagent answer and blocks web calls that contain them. Answers may therefore show `<redacted:secret>`; use the cited path:line to look at the real value yourself only if you must, and never paste it back into a prompt.

The `changelog-summarizer` agent (git history, read-only git commands only) is shipped here because it needs the git guard.
Bulk reads: a hook redirects whole-file reads over the line threshold (default 200, env `BULK_READ_MIN_LINES`) in the main conversation to the `bulk-reader` subagent when that plugin is installed.
Browser agents: `browser-explorer` and `browser-operator` (haiku-delegation) are fenced by a hook. The operator is blocked when its `action_summary` names submit, delete, send, pay, approve, sign, export or publish; if you see that block, stop and ask the user to confirm that exact step. Never route around a guard by driving the browser yourself: the block exists because the step is irreversible or outward-facing, and only the user may approve it.
