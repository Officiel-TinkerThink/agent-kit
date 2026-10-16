# Plan store: apply, cleanup and locking

Scope: plan_store.py, applier.py, cleaner.py, locks.py, models.py.

- R1 Applying a plan version requires that its version is greater than the applied version of the same plan id at the moment the applied state is written.
- R2 Two concurrent applies of the same plan id must never leave an older version as the applied state.
- R3 Cleanup never removes a pending row.
- R4 Locks are acquired in the order given in locks.py (plan before store). No code path requests the plan lock while holding the store lock.
- R5 Cleanup removes only applied history rows, and only those below the latest applied seq of the same plan id.
- R6 apply_next for a plan id with no pending row returns NOTHING_PENDING and changes no state.
