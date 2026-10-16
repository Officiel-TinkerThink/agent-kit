Intent: raise BATCH_SIZE back to 1000 to cut request count for large tenants, and apply the retry backoff cap drop to 20s.
Scope: constants only; no logic change.
