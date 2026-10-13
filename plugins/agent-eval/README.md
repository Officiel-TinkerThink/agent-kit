# agent-eval

Four layers, only the first two automatic:
1. `subagent-usage-log` (SubagentStop) writes one record per run with tokens, tools, duration, effort and deterministic checks (missing answer, invalid JSON, reconciliation mismatch, citations to missing files or lines beyond the file, secret-shaped text, forbidden verdicts, missing footers, secret-guard events).
2. The `annotator` agent (Haiku 5.5, max effort): the main model passes it a failed run; it verifies the claim against the recorded run and writes one annotation. It can only write new JSON files into its inbox and run the plugin's `annotate.py` (guarded).
3. `agent_eval.py judge` (you run it): a stronger model checks queued cases.
4. `agent_eval.py review` (you run it): you confirm or reject; only human reviews make a case confirmed.

See the top-level README for the data folder and the operator routine. Logs reference transcripts by path and SHA-256 and never copy prompts or answers.
