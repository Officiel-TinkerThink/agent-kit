# LAB-214: dose rounding, dispensing windows, keyset listing

R1. Dose labels show mg rounded half-up to the requested number of decimal places (default 2). Input is Decimal, int or str; float input is rejected. Negative doses are rejected.
R2. A dispensing window for a range of site-local days is half-open in UTC: the start is included, the end is excluded. The first day starts at local midnight and the range ends at local midnight after the last day. Window length follows the real elapsed time, including DST changes.
R3. A position in a dispensing window is tested with in_window; an aware UTC datetime is required.
R4. Batch record listings are ordered by (created_at, id). created_at and id are strings. The page token is opaque; a malformed token raises ValueError.
R5. Page size defaults to 50 when not given and is clamped to the range 1..200.
R6. Predicates for status filters are built per value; each predicate keeps its own value.
R7. Stale cache entries are removed when their age is strictly greater than the time-to-live.
R8. Registered report handler names are unique per registry; replace requires an existing name.
