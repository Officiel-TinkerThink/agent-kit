# Spec: Sample label generator (label.py)

Module: `code/label.py`. Register file: CSV, one label per row.

1. **R1** `make_label(sample_id, study_code, collected_at)` returns `STUDY-NNNNNN-YYYYMMDD`, where `NNNNNN` is `sample_id` zero-padded to six digits and `YYYYMMDD` is the date `collected_at`.
2. **R2** `make_label` raises `ValueError` unless `sample_id` is a positive integer no greater than 999999.
3. **R3** `make_label` raises `ValueError` unless `study_code` consists only of uppercase letters and digits and has length 3 to 8 inclusive.
4. **R4** `make_label_batch(study_code, start_id, count, collected_at)` returns `count` consecutive labels starting at `start_id`. `count` must be between 1 and 500 inclusive; otherwise raise `ValueError`.
5. **R5** `make_label` raises `ValueError` when the generated label is longer than 40 characters.
6. **R6** `run_batch(...)` generates the batch, appends every label to the register CSV at `register_path` using `register_labels`, and then returns the labels.
