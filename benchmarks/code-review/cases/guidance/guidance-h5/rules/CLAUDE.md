# Project rules

## Audit trail
- Record every audit event with audit_log.record_event(event, **fields). The audit_log module is the audit writer for lot records.
- The legacy_log module was removed in the last release; do not import it or call it.

## Public API documentation
- Every public function (name not starting with an underscore) needs a docstring.
- Functions should ideally stay under 40 lines. This is a goal for readability, not a gate.
