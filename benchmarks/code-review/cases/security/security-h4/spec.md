# Report download feature

Scope: lab reporting service, analyst workspace.
Modules: config.py, files.py, reports.py, accounts.py, routes.py.

R1. download_report(conn, user, report_id) returns the stored PDF of report_id as a chunk stream, with content type application/pdf, a size, and a SHA-256 digest of the file.
R2. The resolved file path must be REPORT_CACHE_ROOT itself or a path below it. Any other path raises PathContainmentError before the file is opened.
R3. A report may be read only by its owner or by a user with is_admin set. get_report and download_report apply the same rule. A denied request raises PermissionError.
R4. list_reports returns only rows the caller may read.
R5. update_profile accepts only display_name and email from the client payload. role and is_admin are never taken from the client payload.
R6. Every successful download writes one row to audit_log in the same request.
R7. A request without an authenticated user is rejected before any action runs.
R8. Request bodies larger than MAX_PAYLOAD_BYTES are rejected before JSON parsing.
