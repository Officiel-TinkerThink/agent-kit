---
description: Copy the SUBAGENTS.md roster (which subagent to use, standing handoffs, annotate failed runs) into the current project root and import it from CLAUDE.md or AGENTS.md.
argument-hint: "[update] [claude|agents] [dry-run] [path to the project]"
disable-model-invocation: true
allowed-tools: Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/subagents-init *)
---

The user ran this to set up delegation in the current project. The tool never overwrites existing text: it creates `SUBAGENTS.md`, adds one `@SUBAGENTS.md` import line, and reports what it did.

1. Map $ARGUMENTS to flags: `update` -> `-Update`, `dry-run` -> `-DryRun`, `claude` or `agents` -> `-Import claude|agents`, a folder path -> `-Project "<path>"`. No arguments means the git top level of the current folder, import into `CLAUDE.md` if it exists, else `AGENTS.md`, else a new `CLAUDE.md`.
2. If the user did not say `dry-run` and the project already has a `SUBAGENTS.md`, start with a dry run so the user sees what would change. Never add `-Update` on your own: refreshing replaces the shipped part of the file (the project's "Project facts" section is kept and a `.bak-<timestamp>` copy is written), so only use it when the user asked for it.
3. Run exactly:
   `sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/subagents-init [-Project "<path>"] [-Import claude|agents] [-Update] [-DryRun]`
   A `REFUSED:` message is final: report it and do not work around it by editing the files yourself.
4. Report the lines it printed (`CREATED`, `UNCHANGED`, `EXISTS`, `UPDATED`, `IMPORT added/already/created`, `ROOT`). `EXISTS` means the project's file differs from the shipped one and was left alone; offer `update` once, do not run it.
5. Tell the user the one thing left to do by hand: fill in the "Project facts" section at the bottom of `SUBAGENTS.md` (layout and stale folders, files agents must never read, the one command per verification gate). Offer to draft it with `code-explorer` (`Task kind: locate`), but write only what the user confirms. Nothing is committed.
