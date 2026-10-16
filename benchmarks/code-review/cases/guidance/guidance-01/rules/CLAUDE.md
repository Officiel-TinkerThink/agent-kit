# Project Rules (lab batch record service)

1. Never call `datetime.now()` or `datetime.utcnow()` directly. Obtain timestamps from `lab_core.clock.utc_now_iso()`.
2. Domain validation failures raise `DomainError` from `lab_core.errors`. Never raise `ValueError` or `TypeError` in domain code.
3. Every batch record mutation goes through `lab_core.audit.record_change()`. Never write to the store directly.
4. Sample identifiers (`sample_id`, `batch_id`) are passed as `str`. Never coerce them with `int()`.
5. Concentration values are `Decimal`. Never use `float` for concentration. A line carrying `# rule-5-exempt: <reason>` is exempt.
