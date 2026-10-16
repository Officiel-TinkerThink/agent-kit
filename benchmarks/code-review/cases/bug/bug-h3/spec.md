# Sample export: paged CSV and sort option

Intent: the stability review pack needs every retained sample exported to CSV, read in pages, with an optional sort by collection time or by assay score.

- R1 export_csv(repo, out) writes the header row CSV_HEADER, then one row per stored sample. Every stored sample appears exactly once.
- R2 export_csv(..., page_size=N) reads the repository in windows of N rows. The final window, even when shorter than N, is written.
- R3 sort_by=None keeps the repository listing order.
- R4 sort_by="collected" orders rows by created_at ascending, then sample_id ascending.
- R5 sort_by="score" orders rows by assay score ascending. For any two samples with different scores, the sample with the lower score is written first, whatever the size of the difference.
- R6 The repository listing order (list_all, list_page, ids) is total: created_at ascending, then sample_id ascending. Samples with equal created_at are never ordered by insertion order.
- R7 page_size that is not an integer in 1..1000 raises ValueError before any output is written.
- R8 An unknown sort_by value raises ValueError before any output is written.
