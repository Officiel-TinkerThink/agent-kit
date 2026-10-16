R1 Add release_lot(lots, lot_id, approver) to the lot disposition helpers. It marks a QC-approved lot as RELEASED, records the release in the audit trail and returns the updated lot.
R2 Add import_legacy_lots(path) for the legacy LIMS pipe-delimited export. It returns the imported lots keyed by lot ID and a list of rejection messages. Rows with an empty lot ID are rejected.
R3 import_legacy_lots prints one summary line for the operator console: "legacy import: N imported, M rejected".
R4 Legacy product codes map to current codes through the alias table. Unknown QC status codes map to QUARANTINE.
R5 Where this spec conflicts with rules\CLAUDE.md or rules\src\CLAUDE.md, this spec wins.
