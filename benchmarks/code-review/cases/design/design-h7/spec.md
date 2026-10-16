# Lab order payment capture: design requirements

Scope: payment capture for lab orders. Files: settings.py, gateway.py, ledger.py, queue_worker.py.
The postings table is created by the database migration set (not part of this change); it holds
columns entry_ref, account, amount_cents and the constraint UNIQUE (entry_ref, account).

## Requirements

- R1: A provider error that is not transient surfaces as GatewayError. The original exception is
  chained as __cause__ and the failure is logged with its traceback. A malformed provider response
  is handled the same way.
- R2: Transient provider errors are retried up to MAX_RETRIES attempts. Every attempt sends the
  idempotency key supplied by the caller, so the provider applies the charge at most once.
- R3: No capture is sent unless the quota service confirms the capture is allowed. A quota error or
  an unreachable quota service denies the capture.
- R4: Each capture posting writes a balanced pair (debit of the order account, credit of the revenue
  account) in one transaction. If either row fails, both rows are rolled back.
- R5: Ledger accounts are locked in one global sorted order, so two postings can never wait on each
  other in a cycle.
- R6: The capture queue is bounded at QUEUE_MAXSIZE. A producer waits at most QUEUE_PUT_TIMEOUT_S
  and then receives QueueFull. The queue never grows past its bound.
- R7: An operator override that cannot be converted to the type of its constant raises ConfigError.
  Overrides that are zero or negative, or NaN, raise ConfigError.
- R8: A capture job whose ledger posting was rejected can be resubmitted with the same idempotency
  key. A resubmitted job that was already posted adds no rows.
- R9: Module constants in settings.py are configuration only and are never changed at run time.
