# Instrument event intake: requirements

Scope: admission of lab instrument events per site against a daily quota, queueing, and
write-out to the append-only audit store.

R1. EventWorker.submit() admits a batch for a site only when used_today + batch size is less than or equal to SITE_DAILY_EVENT_QUOTA.
R2. When the quota service cannot answer (timeout, connection error, non-200 status), the batch is rejected with QuotaExceeded, nothing is queued, and the rejection is logged.
R3. The pending queue is bounded at QUEUE_MAX_DEPTH events (production default 5000), defined in settings.py. Putting an event beyond the bound raises QueueFull and the event is not queued.
R4. A batch is acknowledged (mark_done) only after the audit store confirms the write. If the store write raises, the batch is restored to the pending queue, the error is logged, and the error text is visible in stats()["last_error"].
R5. Quota windows are UTC calendar days.
R6. A store write error is never reported as processed events in written_total or in the acknowledgement.
R7. Each audit record carries event_id, site_id, instrument_id, recorded_at and payload, and records are only appended.
