# Future improvements

Planned work, in priority order. Each item lists the first step, not a full design. Items move out of this file when they become a PR.

## Priority

| Order | Item | Status | First step |
|---|---|---|---|
| 1 | Knowledge hub (OKF, Open Knowledge Format) | planned | Define the entry schema and a 50-question retrieval test |
| 2 | Browser control (own MCP, replacing or complementing claude-in-chrome) | planned | Time one fixed task with claude-in-chrome and with the friends' tool |
| 3 | Sub-subagent delegation | planned | Confirm the nesting limit, then a one-level experiment against the flat version |
| 4 | Decentralised agent teams | later | Define success metrics, then a repeat-run baseline |
| 5 | Language-specific review lenses (Python first) | deferred, after a leak incident | Add a language gate and a non-Python case set first |

## 5. Language-specific review lenses (deferred)

A Python defect lens was drafted and removed from PR #12. It was written while every benchmark case was Python, so the benchmark could not show it generalised. It was preloaded into every defect review regardless of language, and the leak audit that should have caught it did not cover it.

Before any language lens returns:
- A language gate: the lens applies only when the code under review is in that language. The reviewer checks this first and skips the lens otherwise.
- A leak audit over every answer-key axis, read in full, not by targeted search. The audit target list must be generated from the skills folder, so a new skill cannot skip it.
- A non-Python case set, so a language lens is measured on the language it targets and on the others, where it must add no false positives.
- Each catalogue entry states a general consideration, not an example taken from a case.

## 1. Knowledge hub (OKF)

Goal: a company-brain style knowledge hub that AI agents can read and maintain. It holds rulebooks, guidelines and best practices, and the entries must not duplicate each other and must stay connected as the corpus grows.

Design points:
- Stable IDs. One canonical statement per rule; other documents link to it, they do not copy it.
- Typed links, for example `supersedes`, `conflicts_with`, `implements`, `derived_from`. Untyped "related" links are not enough to resolve which rule wins.
- Provenance on every entry: source document, version, effective date, owner, review status (draft or approved).
- Agents may draft entries and flag duplicates. A human approves. An unapproved rule must not be cited as authoritative.
- Deduplication by similarity alone is not allowed: it merges rules that differ in one condition.
- Measure retrieval with a gold question set (expected rule IDs per question), tracked over time, the same way as the code-review benchmark.

Start small: one domain (for example the CSV checklist or the code-review rules), 30 to 50 entries, the schema, and the retrieval test. Grow only after the test passes.

Open question: the exact OKF specification to follow. Confirm before the schema is fixed.

## 2. Browser control

Goal: faster, more accurate browser control than claude-in-chrome, which is currently slow and limited.

Design points:
- Measure first. Time one fixed task (open a page, read a table, click one control) with claude-in-chrome and the friends' tool. Record seconds per action, success rate and tool calls per task.
- Find where the latency is: screenshots, the round trip per action, or the model. Only the first two are tool problems.
- Choose the transport on the numbers. An extension is not automatically faster than a CDP or Playwright-based MCP server, and an extension adds an install and update step on every workstation.
- Start read-only: page text, element find, network and console reads. Add clicks and form fills only after the read path is measured and trusted.
- Reuse the existing browser guards (host allowlist, read-only default, audit trail, no credential entry) rather than designing a new policy.
- Prompt injection: text on a page can steer the agent. Treat page content as data.
- GxP: a tool that changes records in a web application is a change to a computerised system. It needs a risk assessment and validation evidence before it touches real records.

## 3. Sub-subagent delegation

Goal: keep long-running general-purpose agents' context small by letting them delegate sub-tasks.

Design points:
- The 5-minute figure is the prompt-cache TTL. It affects cost, not whether a subagent can run longer: after a pause the next turn re-bills the whole context at full input price. It is not a time limit on the work.
- Confirm whether the runtime allows a subagent to call the Agent tool, and whether a depth limit applies. Assume one level only until confirmed.
- Delegation adds coordination cost: each hop loses context, and the parent must still verify the child's claims.
- Cheaper alternative first: split long tasks into more independent units at the top level, have each unit write results to a file, and read only summaries in the parent.
- Add a turn budget and a checkpoint file to any long-running agent, so a hard stop returns a partial report.
- Experiment: one level of nesting against the flat version on the same tasks, measured for cost, wall-clock time and correctness, with at least three runs.

## 4. Decentralised agent teams

Goal: teams of agents that help each other, with an adversarial role, for better, faster and more accurate results.

Design points:
- Keep hub-and-spoke as the default. It gives one accountable point and one place for verification.
- Strengthen the existing adversarial role (`finding-validator`) before adding a peer agent.
- A useful decentralised pattern is an independent ensemble, not a conversation: two agents solve the same unit separately, and a third compares them. Measure agreement and error rate against a single agent.
- Peer-to-peer messaging between agents is not planned: shared state causes duplicate work, conflicting edits and agreement bias, where two agents confirm each other's error.
- Define the metrics first: defects found, false positives, wall-clock time, tokens per accepted finding. Measure the current system, then test one change at a time.
- Variance is large (about ±3 defects on identical text in the round-2 runs). Any team change needs at least three runs before a gain is claimed.
