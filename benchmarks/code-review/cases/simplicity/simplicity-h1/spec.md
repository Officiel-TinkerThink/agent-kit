# QC inventory helper tidy-up

Intent: tidy the QC inventory helper modules. Behaviour must be identical to
the previous helpers. Public names, signatures and exceptions are kept.

## Requirements

- R1 (status.py): `is_expired(item, today)` returns True when `item.expiry_date`
  is strictly before `today`, otherwise False.
- R2 (status.py): `is_releasable(item, today)` returns True only when
  `item.status` is QUARANTINE and the lot is not expired.
- R3 (status.py): `releasable_lots(items, today)` returns the lots for which
  `is_releasable` is True, in input order.
- R4 (totals.py): `batch_totals(volumes)` validates the volumes, then returns
  `(sum of volumes, largest single volume)`; `(0, None)` for an empty list.
- R5 (totals.py): `remaining_capacity(capacity_ml, volume_ml)` returns the free
  millilitres of a pool, never below 0.
- R6 (paths.py): `archive_path(batch_id)` returns `ARCHIVE_ROOT + "/" + batch_id + ".json"`
  for a valid batch id and raises ValueError otherwise.
- R7 (paths.py): `batch_id_from_archive_name(file_name)` returns the batch id of a
  `<batch_id>.json` archive name and raises ValueError otherwise.
- R8 (filters.py): `export_targets(batch_ids)` returns `archive_path` for each id
  in input order.
- R9 (filters.py): `variance_limit(limit_ml, default_ml)` returns `default_ml`
  only when `limit_ml` is None; an explicit 0 is returned as 0.
- R10 (filters.py): `label_text(item)` returns the upper-case lot number, or None
  when the lot number is empty.
