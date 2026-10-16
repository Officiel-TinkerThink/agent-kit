# Spec: Batch record QA sign-off (batch_signoff.py)

Module: `code/batch_signoff.py`. A batch record is a dict with keys `status`, `operator_id`, `batch_id`, `signature`, `history`.

1. **R1** `sign_off(record, user)` raises `ValueError` unless `record["status"]` is `"REVIEWED"`. On success it sets `record["status"]` to `"SIGNED"`.
2. **R2** `sign_off` raises `PermissionError` unless `user["role"]` is `"QA"` and `user["id"]` differs from `record["operator_id"]`.
3. **R3** On success `sign_off` sets `record["signature"]` to a dict with keys `user_id` (the signing user's id) and `timestamp` (current UTC time in ISO 8601 format).
4. **R4** `update_field(record, field, value)` raises `PermissionError` when `record["status"]` is `"SIGNED"`. Otherwise it sets the field and returns the record.
5. **R5** On success `sign_off` appends `{"action": "SIGN_OFF", "user_id": <signing user id>}` to `record["history"]`.
