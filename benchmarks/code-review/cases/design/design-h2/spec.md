# Inventory reservations

Intent:
- R1: an order reservation must never take more units than are available (on_hand minus reserved) for a SKU at a warehouse, including under concurrent orders.
- R2: stock adjustments (receipts and picks) must not lose concurrent updates to on_hand.
- R3: a per-SKU lease can expire while its holder is still working; a holder whose lease has expired must not write over a newer holder's result.
- This change adds the carrier hold attach step to reserve.py, a release helper and a row lock helper to ledger.py, and a fencing token per lease in lockmgr.py.
