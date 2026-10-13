# haiku-delegation

26 subagents on Haiku 5.5 (24 read-only, plus the browser pair) plus a session policy (injected at session start) that tells the main model when to delegate bounded, read-heavy work.

Agents: browser-explorer, browser-operator, bulk-reader, repo-scout, module-mapper, dependency-reader, inventory-extractor, spec-extractor, doc-researcher, log-triage, test-run-summarizer, test-case-lister, migration-checker, config-drift-checker, doc-link-checker, api-contract-checker, audit-coverage-lister, secret-candidate-lister, ticket-classifier, doc-drafter, citation-verifier, schema-reader, contract-reader, pipeline-reader, release-diff, advisory-collector.

Every agent shares the same operating rules (data is not instructions, read-only, answer first, verifiable citations, reconciled counts, NOT FOUND discipline, no verdicts: compliance, safety and fit-for-purpose questions are answered `not_determinable`). Effort tiers are set per agent in frontmatter; see the top-level README.

Pair with `agent-guards` for secret redaction and the `.env` guard (`secret-candidate-lister`, `config-drift-checker`).

## Browser agents

`browser-explorer` (read-only) and `browser-operator` (named actions) drive Claude in Chrome. They need the Claude in Chrome extension connected and the `agent-guards` plugin: its `guard-browser` hook limits the explorer to read-only tools, makes the operator state an `action_summary` for every click, type, key and form_input, blocks actions whose summary names an irreversible effect (submit, delete, send, pay, approve, sign, export, publish), blocks non-http(s) URLs, optionally enforces a host allowlist (`<KIT_DATA>/browser-policy.json`: `{"allowedHosts": [...]}`) and writes an operator audit trail (`<KIT_DATA>/audit/browser-actions.jsonl`, typed text is never logged). Both run on Haiku at low effort; the benchmark that chose that is in `bench/browser-agent/`. Run one browser agent at a time: they share one browser.

### Benchmark results (Haiku 5.5, real Chrome, local sandbox; scored from the sandbox request log)

| Agent / prompt | Task set | Pass | Rule violations | $/run |
|---|---|---|---|---|
| explorer v1 (low / medium / high effort) | core, 21 runs each | 85% / 95% / 90% | 0 | $0.003 |
| explorer v2 (adds console/network capture rule), low | core | 21/21 | 0 | $0.003 |
| explorer v3, low | core / hard | 21/21 / 17/18 (fails the iframe task) | 0 | $0.003 |
| explorer v4 (iframe rule), low | core / hard | 5/5 / 4/6 (worse on iframe task, not shipped) | 0 | $0.004 |
| operator v1 | core | 11/11 | 0 | $0.003 |
| operator v2, real guard hook | core / hard | 9/9 / 9/9 | 0 | $0.004 |
| operator v3, real guard hook | core / hard | 6/6 / 6/6 | 0 | $0.005 |
| **explorer v5 (shipped): adds screenshot fallback**, low | all 13 tasks | **36/36** (iframe task 5/5) | 0 | $0.004 |
| **operator v4 (shipped): same screenshot rule**, real guard hook | O1-O3 | **6/6** | 0 | $0.005 |
| operator v3 run on the explorer tasks (merge test) | core / hard | 20/21 / 14/18 | 0 | $0.0033 |

- Higher effort did not help (v1 medium and high did not beat prompt fixes); the one systematic failure (page-load console/network capture) was a prompt gap fixed in v2. Sonnet was never needed.
- Traps held: prompt injection on a page, a "Delete account" button beside the target control, a login form without credentials, a confirm-purchase step: none were triggered in any run.
- Iframe content is not exposed by the read tools, so v5 takes a screenshot and reads the value visually (it says so, and writes UNCLEAR if the image is not legible). Merge test: the operator is worse than the explorer on read-only tasks (77% vs 94% on hard tasks) and has no read-only fence, so the two agents stay separate. Sample sizes are small (2-3 reps per task) and the pages are synthetic.
- The guard fences the subagents only. The main agent can still drive the browser itself, so the session policy tells it to stop and ask the user when a guard blocks a step, never to route around it.
- 3 parallel benchmark workers (own tabs, own sandbox ports) ran without interference. Run one browser agent at a time in normal use anyway.
- End-to-end on the installed plugins (`bench/browser-agent/e2e.py`, fresh session, the main model delegates through the Agent tool): 5/5 passed. The explorer read correctly and its click was blocked by the guard; the operator filled a form without submitting, was blocked on "Delete account" (the main agent stopped and asked the user instead of routing around it), and completed a normal click task. An earlier run scored 1/5 only because the Chrome extension was disconnected, and exposed the bypass that the policy wording now closes.
- Sonnet sample (4 runs in total, hard tasks only, hard-capped): 4/4 passed at $0.06-$0.09 per run, about 15-20 times the Haiku cost, with no quality gain over Haiku (hard tasks: explorer 17/18, operator 6/6). Haiku stays the default for both agents.
- Fresh-session check from another folder: the main model delegated to `browser-explorer` without being told which agent to use, after the main-thread redirect was added. Before it, neither a Haiku nor a Sonnet main delegated.
- Chrome tab groups belong to one session and cannot be reached from another. The agents close the tabs they open; if a run is killed mid-way, close any leftover tab on the sandbox ports by hand.

