# Payment capture with retries: intent and requirements

Intent: order intake captures a card payment through the payment gateway with bounded retries, never charges a customer twice for one attempt chain, and reports failures with their cause.

- R1 A payment capture that is retried after a transport failure must not create a second charge for the same order request. All attempts of one capture share one Idempotency-Key.
- R2 Every outbound payment and order-gateway call uses a finite timeout taken from configuration or a named constant.
- R3 Only transient failures (timeouts, connection errors, HTTP 429 and 5xx) are retried. A validation rejection (HTTP 422) is not retried.
- R4 When retries are exhausted, the raised PaymentError carries the last failure as its cause.
- R5 Order and payment state transitions are read from the stored order; the status shown in the confirmation payload equals the stored status.
