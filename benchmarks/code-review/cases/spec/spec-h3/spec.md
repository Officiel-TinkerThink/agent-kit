# Batch release workflow specification

Scope: release of a batch record in the batch release workflow (states.py, release.py, units.py).

Requirements:

- R1: Batch status codes are SIGNED=3, RELEASED=5, REJECTED=7. Code 4 is retired and must be rejected with ValueError. It must never be mapped to a status.
- R2: Release requires status SIGNED and a QA signer that differs from the operator.
- R3: A release stores the quantity in micrograms as an integer, converting from the given unit (mg or ug).
- R4: A quantity of 0 is invalid and raises ValueError. A missing quantity (None) raises TypeError.
- R5: Release is idempotent. Releasing an already RELEASED batch with the same signer returns the existing record and writes no second audit entry.
- R6: Every release writes exactly one audit entry containing the batch id, the signer and the micrograms.
- R7: A rejected batch can never be released.
