# Project Rules (photometer calibration tools)

1. Domain code under `code/` raises `DomainError` from `lab_core.errors` for invalid input. Never raise `ValueError`.
2. Every calibration record mutation goes through `lab_core.audit.record_change()`.
3. Rules for services/ only: HTTP handlers in `services/` return an RFC 7807 problem body on error and call `lab_core.clock.utc_now_iso()` instead of `datetime.now()`.
4. Concentration and absorbance values are `Decimal`. Never use `float`.
5. Public functions in `code/` have a docstring with a one-line summary.
