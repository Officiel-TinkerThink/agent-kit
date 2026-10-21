# Contributing

For people and for agents that open pull requests in this repository.

## The rule in one paragraph

A pull request **adds its changelog line** under `## [Unreleased]` in `CHANGELOG.md` and **does not bump any version**. Versions are bumped once, in a separate release step by a maintainer, when `main` is ready to ship. Why: seven files carry the version (six `plugin.json` and `.claude-plugin/marketplace.json`), so PRs that each bump it conflict with one another and claim the same number; and the changelog text is best written by the author while the reason for the change is still known.

## Opening a pull request

1. Branch from `main`. One topic per PR.
2. Make the change. Add or update tests; run the suites that cover what you touched (`python tests/run_all.py`, or one file such as `python tests/haiku-delegation/test_changelog.py`).
3. Add the changelog line (rules below).
4. If you edited the root `SUBAGENTS.md`, copy it to `plugins/haiku-delegation/templates/SUBAGENTS.md` too. If you edited the root `AGENTS.md`, copy it to `plugins/haiku-delegation/templates/AGENTS.md` too. A test fails when either pair differs.
5. Open the PR with the template filled in: what and why, how it was verified (commands and results, not "tested"), the changelog line, and a link to the change-control record when the team has one.
6. Do not edit `version` in any `plugin.json` or in `marketplace.json`. Do not rename `[Unreleased]`.

## Changelog line

- **Place:** under `## [Unreleased]`, in one group: `Added`, `Changed`, `Fixed`, `Removed` or `Security`. Create the group if it is missing.
- **Write for users and operators**, in plain words: what they will see, on which platform, and since when. "Ubuntu never wrote a usage record; the hook now forces `LC_ALL=C`" is right. "Set LC_ALL" is not.
- **Name the command, file or setting** a reader would look for (for example `/haiku-delegation:subagents-init`, `usage/agent-usage.jsonl`).
- **Mark breaking changes** with `**Breaking:**` at the start of the line, and say what to do about it.
- **Skip** refactors with no visible effect, test-only changes to existing tests, formatting and typo fixes. A PR with nothing user-visible says so in the template instead of adding a line.
- **Security fixes** go under `Security`, described by class and effect, never with a working exploit.
- **GxP:** the changelog is for readers; it does not replace the QMS change record. When a change-control ID exists, put it at the end of the line, for example `(CC-1234)`.

## Release step (maintainer, or an agent the maintainer asked)

Done in its own commit or PR titled `release X.Y.Z`, after the feature PRs are merged:

1. In `CHANGELOG.md`: rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and add a new empty `## [Unreleased]` above it.
2. Set `"version": "X.Y.Z"` in all six `plugins/*/.claude-plugin/plugin.json` and all six entries of `.claude-plugin/marketplace.json`. Installed plugins update only when this number changes, so a merge users should receive needs a release.
3. Run `python tests/haiku-delegation/test_changelog.py` (versions and changelog agree) and the full suite.
4. Merge, then tag `vX.Y.Z` on the merge commit.

Version numbers: while below 1.0 a new feature or fix bumps the patch number; a breaking change bumps the minor number.

## For agents

- You write the changelog line in the PR you open. You never bump versions and never rename `[Unreleased]` unless the user told you to cut a release.
- Report what you verified, with the command and its result. If a test was skipped or failed, say so.
- Do not merge your own PR unless the user told you to; state in the PR what you ran so the reviewer can check it.
