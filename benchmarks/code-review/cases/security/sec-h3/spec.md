# sec-h3 intent: batch record reporting (export, query, render)
R1. CSV exports are opened in spreadsheet software: a text cell whose first non-blank character is a formula prefix (=, +, -, @) must be written with a neutralising prefix.
R2. Batch lookups by id accept request values; every id must be validated as an integer, and request values reach SQL only as bound parameters or validated integers.
R3. Report titles are user-supplied: they are shown as text in HTML and are never evaluated as template syntax.
R4. Row limits from requests are clamped to the range 1..500.
