# Change intent: report service source feeds, job queue and result cache

The change adds source-feed fetching, job enqueueing and export of report rows, and a cache for report results.

R1. Every outbound HTTP call sets an explicit timeout no larger than REQUEST_TIMEOUT_SECONDS.
R2. Every file handle and database cursor opened by a job is released on success and on every exception path.
R3. Retries use bounded attempts with jittered backoff.
R4. Report results are cached for REPORT_TTL_SECONDS; concurrent misses for the same key compute the value once.
R5. Enqueueing a job never blocks longer than ENQUEUE_TIMEOUT_SECONDS.
