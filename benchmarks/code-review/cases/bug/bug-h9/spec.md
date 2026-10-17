# Intent

Intent: Add a batch entry point for the payment worker that runs charges on up to 8 threads.
Each payment request carries an idempotency key. A charge for a given key must run at most once,
including when the client sends the same key twice at the same time to parallel workers.
A repeated key must return the same receipt as the first request, without a second gateway charge.
Invalid requests (missing key, amount outside 1..1000000 cents) must be rejected before any charge runs.
