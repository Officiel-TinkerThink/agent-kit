"""User records, profile updates and report access rules."""

import logging
from dataclasses import asdict, dataclass

from config import ROLE_ANALYST, USER_FIELDS

log = logging.getLogger("labrpt.accounts")


@dataclass
class User:
    """Authenticated user identity as used by the report services."""

    user_id: int
    display_name: str
    email: str
    role: str = ROLE_ANALYST
    is_admin: bool = False


def find_user(conn, email):
    """Look up a user by e-mail address using a bound parameter."""
    row = conn.execute(
        "SELECT user_id, display_name, email, role, is_admin FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    return None if row is None else build_user_from_row(row)


def build_user_from_row(row):
    """Construct a User from a database row, keeping only the known columns."""
    return User(**{key: row[key] for key in USER_FIELDS})


def update_profile(user, payload):
    """Apply a client profile payload and return the updated user."""
    merged = {**asdict(user), **payload}
    log.info("update_profile user=%s fields=%s", user.user_id, sorted(payload))
    return User(**merged)


def save_user(conn, user):
    """Persist the user's profile and role columns."""
    conn.execute(
        "UPDATE users SET display_name = ?, email = ?, role = ?, is_admin = ? WHERE user_id = ?",
        (user.display_name, user.email, user.role, int(user.is_admin), user.user_id),
    )
    conn.commit()
    log.info("save_user user=%s", user.user_id)


def can_read_report(user, report):
    """Owners and administrators may read a report; other users may not."""
    return user.is_admin or report["owner_id"] == user.user_id


def verify_session_token(stored_token, presented_token):
    """Return True when the presented session token matches the stored token."""
    return presented_token is not None and stored_token == presented_token
