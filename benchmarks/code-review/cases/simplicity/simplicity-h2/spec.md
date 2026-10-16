# labops-export: CSV output for released batch records

Owner: Lab Operations Tooling. Scope: `exporter.py` and `cli.py` change; other modules unchanged.

## Requirements

- R1: `--format` accepts `json` (default) and `csv`.
- R2: CSV output has one header row, then one row per batch, columns in this order: `batch_id, product_code, yield_pct, status, released_on`.
- R3: The CSV header row is written on every CSV export.
- R4: `yield_pct` is rounded to 2 decimal places in both formats.
- R5: JSON output stays byte-identical to the previous release for the same input and settings.
- R6: CSV rows use LF line endings and the configured encoding (`LABOPS_EXPORT_ENCODING`).
- R7: The output file extension equals the format name; the file is written to `LABOPS_EXPORT_OUTPUT_DIR` with the prefix `LABOPS_EXPORT_FILE_PREFIX`.
- R8: The number of exported rows is capped by `LABOPS_EXPORT_MAX_ROWS` and by `--limit`; the lower value wins; `--limit 0` exports no rows.
- R9: Helper functions in `exporter.py` that other jobs import keep their current signatures and output.
