---
description: Check that the agent-kit data folder, policy files, hooks and installed versions are healthy; use when a hook or subagent misbehaves, after an update, or when audit or usage records seem missing.
argument-hint: ""
allowed-tools: Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/kit-doctor)
---

Run:
`sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/kit-doctor`

It is read-only apart from a probe file per folder that it removes again. Report the result as a short table: each `[FAIL]` and `[WARN]` with what it means and the one action that fixes it; summarise the `[OK]` lines in one sentence.

Typical actions:
- `KIT_DATA split` or `environment`: set `AGENT_KIT_DATA` to one folder, or move the data into the folder the hooks resolve.
- `writable` FAIL: the audit or usage records are being lost. Fix permissions or the path first; nothing else is trustworthy until this passes.
- policy `integrity` WARN: the file was edited outside `/agent-guards:kit-allow`. Ask the user whether the change was intended; if it was, it can be recorded again through `/agent-guards:kit-allow` with a reason.
- `blocked requests`: the user can review them with `/agent-guards:kit-allow`.
- `plugin ...: restart Claude Code`: an update is installed but this session still runs the old version.

Do not edit policy files yourself and do not approve anything on the user's behalf.
