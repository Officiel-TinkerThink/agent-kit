# Spec: Dose rounding utility (dose.py)

Module: `code/dose.py`. Audit sink: `audit_log.record_audit(action, details)`.

1. **R1** `round_dose(amount_mg, step_mg, max_dose_mg)` rounds `amount_mg` to the nearest multiple of `step_mg`. Exact ties (halfway between two multiples) round up.
2. **R2** `round_dose` raises `ValueError` when `amount_mg` is negative, and when `step_mg` or `max_dose_mg` is not greater than zero.
3. **R3** The value returned by `round_dose` never exceeds `max_dose_mg`. If the rounded value would exceed it, return `max_dose_mg`.
4. **R4** `round_order(order)` returns `round_dose` applied to the `amount_mg`, `step_mg` and `max_dose_mg` fields of a `DoseOrder`, with identical results.
5. **R5** Every call to `round_dose` appends one audit entry by calling `audit_log.record_audit("round_dose", details)`, where `details` holds the three inputs and the returned value, before the function returns.
6. **R6** `dose_in_grams(amount_mg)` returns `amount_mg` divided by 1000, without rounding.
