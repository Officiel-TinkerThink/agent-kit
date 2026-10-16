from datetime import datetime, timezone

REVIEWED = "REVIEWED"
SIGNED = "SIGNED"
RELEASED = "RELEASED"


def sign_off(record, user):
    """Apply a QA sign-off to a reviewed batch record."""
    if record["status"] != REVIEWED:
        raise ValueError("record must be REVIEWED before sign-off")
    if user["role"] != "QA":
        raise PermissionError("only QA may sign off")
    record["status"] = SIGNED
    record["signature"] = {
        "user_id": user["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    record.setdefault("history", []).append(
        {"action": "SIGN_OFF", "user_id": user["id"]}
    )
    notify_qa_lead(record)
    return record


def update_field(record, field, value):
    """Update a field unless the record is locked."""
    if record["status"] == RELEASED:
        raise PermissionError("signed record is locked")
    record[field] = value
    return record


def notify_qa_lead(record):
    print(f"QA lead notified for batch {record['batch_id']}")
