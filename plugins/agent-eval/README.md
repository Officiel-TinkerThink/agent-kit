# agent-eval

Four layers, only the first two automatic:
1. `subagent-usage-log` (SubagentStop) writes one record per run with tokens, tools, duration, effort and deterministic checks (missing answer, invalid JSON, reconciliation mismatch, citations to missing files or lines beyond the file, secret-shaped text, forbidden verdicts, missing footers, secret-guard events).
2. The `annotator` agent (Haiku 5.5, max effort): the main model passes it a failed run; it verifies the claim against the recorded run and writes one annotation. It can only write new JSON files into its inbox and run the plugin's `annotate.py` (guarded).
3. `agent_eval.py judge` (you run it): a stronger model checks queued cases.
4. `agent_eval.py review` (you run it): you confirm or reject; only human reviews make a case confirmed.
5. `/agent-eval:report-issue` (you run it): turns `hook-errors.log` and the annotations of the last N days into a draft GitHub issue for the maintainers. The draft holds counts, script names, versions and sanitized messages (home folders, paths, tokens and addresses replaced); never prompts, answers or transcripts. It is shown to you, and sent only after you confirm: with `gh` logged in the skill creates the issue (and first looks for one with the same fingerprint), otherwise it prints a prefilled link for the browser. The repository can be changed with `AGENT_KIT_REPO` for a fork.

See the top-level README for the data folder and the operator routine. Logs reference transcripts by path and SHA-256 and never copy prompts or answers.
