---
description: Copy the SUBAGENTS.md roster (which subagent to use, standing handoffs, annotate failed runs) into the current project root, import it from CLAUDE.md or AGENTS.md, and add the shipped orchestrator rules to that same file as a marked block.
argument-hint: "[update] [claude|agents] [dry-run] [no-orchestration] [path to the project]"
disable-model-invocation: true
allowed-tools: Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/subagents-init *)
---

The user ran this to set up delegation in the current project. The tool never overwrites existing text: it creates `SUBAGENTS.md`, adds one `@SUBAGENTS.md` import line, then appends the orchestrator rules between a `<!-- agent-kit:orchestration:begin ... -->` and a `<!-- agent-kit:orchestration:end -->` line in the same file, and reports what it did. Everything already in that file stays byte for byte, and the rules are never added twice.

1. Map $ARGUMENTS to flags: `update` -> `-Update`, `dry-run` -> `-DryRun`, `no-orchestration` -> `-NoOrchestration`, `claude` or `agents` -> `-Import claude|agents`, a folder path -> `-Project "<path>"`. No arguments means the git top level of the current folder, import and rules into `CLAUDE.md` if it exists, else `AGENTS.md`, else a new `CLAUDE.md`.
2. If the user did not say `dry-run` and the project already has a `SUBAGENTS.md` or a rules block, start with a dry run so the user sees what would change. Never add `-Update` on your own: refreshing replaces the shipped part of `SUBAGENTS.md` (the project's "Project facts" section is kept and a `.bak-<timestamp>` copy is written) and the text between the two markers of the rules block (the target file is backed up first), so only use it when the user asked for it.
3. Run exactly:
   `sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/subagents-init [-Project "<path>"] [-Import claude|agents] [-Update] [-DryRun] [-NoOrchestration]`
   A `REFUSED:` message is final: report it and do not work around it by editing the files yourself. Damaged markers (a begin line without an end line, the end before the begin, two blocks) are refused this way; the user fixes them by hand.
4. Report the lines it printed (`CREATED`, `UNCHANGED`, `EXISTS`, `UPDATED`, `IMPORT added/already/created`, `ORCHESTRATION added/already present/up to date/outdated/updated/skipped`, `WOULD ...`, `ROOT`). `EXISTS` means the project's `SUBAGENTS.md` differs from the shipped one and was left alone; `ORCHESTRATION outdated` means the block differs from the shipped rules and was left alone; offer `update` once for either, do not run it. `ORCHESTRATION already present ... (verbatim; no markers added)` means the same rules were already in the file without markers, so nothing was added.
5. Tell the user the one thing left to do by hand: fill in the "Project facts" section at the bottom of `SUBAGENTS.md` (layout and stale folders, files agents must never read, the one command per verification gate). Offer to draft it with `code-explorer` (`Task kind: locate`), but write only what the user confirms. Nothing is committed.
