# Spec: Retry wrapper with audit entries (retry.py)

Module: `code/retry.py`. `audit` is a list-like object supporting `append(dict)`.

1. **R1** `call_with_retry(fn, audit, max_attempts=3, base_delay_s=0.5)` calls `fn` at most `max_attempts` times and returns the result of the first successful call.
2. **R2** Only `TransientError` is retried. Any other exception raised by `fn` propagates immediately with no further attempts.
3. **R3** Before attempt n+1, the function sleeps `base_delay_s * 2**(n-1)` seconds, where n is the number of the attempt that just failed. No sleep occurs after the final attempt.
4. **R4** Every attempt, whatever its outcome, appends one dict to `audit` with keys `attempt` (1-based attempt number) and `outcome` (`"success"`, `"transient_error"` or `"fatal_error"`).
5. **R5** When the final allowed attempt fails with `TransientError`, that `TransientError` is re-raised to the caller.
