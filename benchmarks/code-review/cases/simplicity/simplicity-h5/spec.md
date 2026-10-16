# Lot capture service: retry, lot lifecycle, input validation

Scope: retry.py, state.py, validate.py, copy_utils.py in the lot capture service.
Change: adds the retry policy with backoff and jitter, the lot transition table with an
audit history, and the sample code parser.

R1 Retry delay. A TransientError is retried until max_attempts total attempts (default 4).
The delay after failed attempt n is base_delay_s * 2**(n-1), capped at max_delay_s (default
8.0 s), then reduced by a random fraction of at most jitter_ratio (default 0.2) so that
concurrent clients do not retry at the same instant. No delay exceeds max_delay_s. No sleep
follows the last failed attempt.

R2 Retry outcome. When every attempt fails with a retryable error, RetriesExhausted is raised
with the attempt count and the last error. Any other exception propagates on the first attempt,
unchanged.

R3 Policy validation. A RetryPolicy with max_attempts < 1, a negative base_delay_s or a
max_delay_s below base_delay_s is rejected at construction with ValueError.

R4 Lot lifecycle. Statuses are DRAFT, REVIEW, RELEASED and REJECTED. Permitted moves are
DRAFT to REVIEW, REVIEW to RELEASED, REVIEW to REJECTED and REJECTED to DRAFT. RELEASED is
terminal. Any other move raises InvalidTransition. can_transition returns False for a terminal
lot and does not raise.

R5 Audit history. Each accepted transition appends a HistoryEntry with sequence, from status,
to status, actor and a copy of the lot items at that moment. Later changes to the lot item list
must not alter stored entries. An empty actor is rejected with ValueError.

R6 Quantity. An untouched quantity field (None) takes the batch default. An explicit 0 is valid
and is stored as 0. Negative, non-integer, boolean and over-maximum values are rejected with
ValidationError.

R7 Lot codes. Input is stripped and upper-cased, then must be 6 to 12 characters of A-Z, 0-9
and hyphen, not starting or ending with a hyphen.

R8 Sample codes. Input is stripped only. Must be exactly 8 characters of a-z and 0-9. Upper
case and hyphens are rejected. Lot code and sample code rules are separate.
