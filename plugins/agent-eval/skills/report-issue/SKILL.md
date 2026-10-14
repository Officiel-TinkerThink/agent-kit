---
description: Turn the kit's local error evidence (hook errors, annotated agent failures) into a GitHub issue for the agent-kit maintainers. Builds a sanitized draft, shows it to you, and files it only after you confirm.
argument-hint: "[days, default 30]"
disable-model-invocation: true
allowed-tools: Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/issue-report *)
---
Report plugin errors to the maintainers. The issue tracker is public, so nothing is sent until the user has read the draft and said yes.

1. Build the draft (sends nothing). `$ARGUMENTS` is an optional number of days:

   sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/issue-report draft [-Days <n>]

   If it prints `NO ERRORS`, tell the user there is nothing to report and stop.
2. Read the `DRAFT <path>` file with the Read tool and show its table to the user in the reply. State plainly what it contains (counts, script names, the kit, plugin, Claude Code and OS versions, sanitized messages) and what it never contains (prompts, answers, transcripts, file contents). Point out anything in it that still looks like private data (a project name, a host name) so the user can edit the file before sending.
3. Ask: "Send this as a GitHub issue to the agent-kit repository?" Do nothing more until the user answers. A "no" ends the skill; the draft stays in the reports folder.
4. On yes, submit the draft (it is sanitized once more, and an issue with the same fingerprint is looked up first):

   sh ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh ${CLAUDE_PLUGIN_ROOT}/scripts/issue-report submit -Draft "<the DRAFT path>"

5. Report the result line: `CREATED <url>`, `DUPLICATE <url>` (nothing created, offer to add a comment), or `NO_GH <link>` (`gh` is missing or not logged in; give the user the link to open in a browser). `REJECTED` or `FAILED` lines go to the user as they are.

Rules: never submit without the user's yes in this conversation; never edit the draft to add content the script did not write; never paste a secret, a prompt or an answer into the draft or the reply.
