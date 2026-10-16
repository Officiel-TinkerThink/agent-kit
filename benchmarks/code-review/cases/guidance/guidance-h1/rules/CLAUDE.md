# Project rules

## Audit trail
- Every public function that writes a record must call audit.record_change(...) before returning.
- A line tagged `# rule-exempt: <ticket> <reason>` is exempt from the rule it breaks; the ticket is required.

## Time
- Timestamps via clock.utc_now_iso().
