# Repository rules

- Every public function that writes a record must call audit.record_change(...) before it returns. Private helpers (leading underscore) may write, because their public caller records the change.
- Do not call datetime.now() or time.time() in production code. Use clock.utc_now_iso(). A single line may opt out only with a trailing `# rule-exempt: <ticket>` comment, and the ticket must be named in the change request.
- Batch-record failures in services\ are reported with ops_feed.push(event, **fields). The ops feed is the failure channel for services\; do not use print() there.
