# Dispensing validators, status labels and report helpers: intent and requirements

Intent: add the station C validators (weight and vial fill), an operator-facing status label lookup, and sample disposition, event handling and dispense mode helpers to the report module. Every rule keeps its own requirement ID so that each check traces to one rule.

- R1 Dispensed weight in grams must be within the inclusive range [WEIGHT_MIN_G, WEIGHT_MAX_G]. A missing, non-numeric or non-finite weight is an error that names the station.
- R2 Vial fill weight in grams must be strictly greater than VIAL_MIN_FILL_G (the pharmacopoeial minimum is exclusive) and at most VIAL_MAX_FILL_G. This rule differs from R1 and stays a separate check.
- R3 Each status code maps to exactly one operator label. A code outside the table shows UNKNOWN_LABEL.
- R4 A sample with no record is REJECT. A sample with a FAIL QC result is REJECT. A sample with a record and no QC result is PENDING. Otherwise the sample is RETEST when a retest is due, and ACCEPT when it is not.
- R5 Event kind ALERT appends the message to alerts. Kind RETRY increments retries and queues the batch. Kind DROP logs a warning and changes no state. Any other kind raises ValueError.
- R6 Dispense mode: a missing line state is LOCKED. A line state with a missing weight is MANUAL. A weight above the limit is SPLIT. Otherwise the mode is SINGLE.
- R7 Status codes are normalised before lookup (strip and upper-case); the normalised value is str or None.
