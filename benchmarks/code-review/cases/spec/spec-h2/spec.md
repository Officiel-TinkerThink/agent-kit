# Specification: batch record listing API

Scope: `api.py` (list_records, export_all), `repo.py` (fetch_page, count_matching), `paging.py` (paging helpers).

## Requirements

- R1: Every public function that returns a page of records uses a page size that defaults to 25 when none is given, and is never above 100. A larger request is clamped to 100.
- R2: Pages are 1-based. Page 1 is the first set of rows.
- R3: Results are ordered by created_at descending, with id descending as the tie-breaker, so that the order is stable across pages.
- R4: The window filter is created_at >= start and created_at < end, with both bounds in UTC. Naive datetimes are rejected.
- R5: The list_records response includes the total count of matching records in the window, not the count of the page.
- R6: An invalid page (less than 1) raises ValueError.
- R7: Each list_records or export_all call writes exactly one audit entry containing the user, the filter and the number of rows returned.
