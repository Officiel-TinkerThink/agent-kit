# Regulated record audit trail specification

Scope: record_store.py, audit.py, api.py, signatures.py and models.py in the records package.

R1. Every create, update and delete of a regulated record writes an audit entry that holds the actor, the server time, the action, the old value and the new value.
R2. Audit entries cannot be edited or deleted after they are written.
R3. A record change never overwrites information without keeping the old value in the audit entry.
R4. An electronic signature entry records the meaning of the signature (approved, reviewed, rejected).
R5. Read operations need no audit entry.
R6. Audit timestamps come from the server clock; a timestamp supplied by the client is never used as the audit time.
