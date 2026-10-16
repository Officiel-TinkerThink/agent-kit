# Spec: batch weight import, report window and batch identifiers

Scope: the scale-station export importer, weight and count parsing, the batch identifier sequence, the report day window and the range helpers.

## Requirements

- R1 `importer.import_file(path, sequences)` reads a semicolon-delimited export with the columns `sample_id`, `weight` and `produced_on` (ISO date). Each row that parses yields one `(batch_id, sample_id, weight_g)` tuple. A row that fails parsing is logged and skipped; the import continues with the next row.
- R2 `parsing.parse_weight` returns grams:
  - plain numbers are taken as they are: `"1234.5"` gives 1234.5;
  - a comma used as a thousands separator together with a decimal point is removed: `"1,234.5"` gives 1234.5;
  - a single comma followed by exactly three digits and no decimal point is a thousands separator: `"1,234"` gives 1234;
  - a single comma followed by one or two digits and no decimal point is a European decimal comma: `"12,5"` gives 12.5;
  - any other text raises `ParseError`.
- R3 `parsing.parse_count` accepts digits only. `parsing.parse_lot_quantity` returns a `Decimal` rounded to two places and rejects negative or non-finite values.
- R4 `report.days_in_range(start, end)` returns the number of calendar days in the window, counting both the start day and the end day. `start == end` returns 1. An end before the start raises `ReportError`. `report.reporting_window_days(records)` returns `days_in_range` over the earliest and the latest `produced_on` of the records.
- R5 `sequences.BatchSequence.next_batch_id(day)` returns the identifier `PREFIX-YYYYMMDD-SUFFIX`. The suffix is the uppercase hexadecimal sequence number of that day, zero-padded to at least two digits. The suffix grows to more digits when the number needs them: number 255 gives `FF`, number 256 gives `100`.
- R6 Identifiers issued for the same day and prefix are unique. One import file may create up to 4096 identifiers for one day.
- R7 `ranges.int_range_inclusive` and `ranges.inclusive_day_count` include both bounds. `ranges.chunked` yields slices of at most `size` items. `ranges.shift_weekday` uses Monday=0.
- R8 Weights below zero are rejected by the report functions with `ReportError`.
