import hashlib
import hmac

from db import get_connection


def hash_password(password):
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def create_analyst(username, password):
    conn = get_connection()
    conn.execute(
        "INSERT INTO analysts (username, pw_digest) VALUES (?, ?)",
        (username, hash_password(password)),
    )
    conn.commit()


def verify_analyst(username, password):
    conn = get_connection()
    row = conn.execute(
        "SELECT pw_digest FROM analysts WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return False
    return hmac.compare_digest(row[0], hash_password(password))
