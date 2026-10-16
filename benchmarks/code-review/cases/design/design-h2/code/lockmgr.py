"""Per-SKU maintenance leases stored in the inventory database."""

import time
import uuid

DEFAULT_TTL_SECONDS = 30


class LeaseUnavailable(Exception):
    pass


class Lease:
    def __init__(self, sku, owner, expires_at, token):
        self.sku = sku
        self.owner = owner
        self.expires_at = expires_at
        self.token = token

    def is_valid(self, now):
        return now < self.expires_at


class LeaseManager:
    def __init__(self, conn, ttl_seconds=DEFAULT_TTL_SECONDS, clock=time.time):
        self._conn = conn
        self._ttl = ttl_seconds
        self._clock = clock

    def acquire(self, sku):
        now = self._clock()
        owner = uuid.uuid4().hex
        expires_at = now + self._ttl
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE sku_leases SET owner = ?, expires_at = ? "
            "WHERE sku = ? AND expires_at <= ?",
            (owner, expires_at, sku, now),
        )
        if cur.rowcount == 0:
            cur.execute(
                "INSERT OR IGNORE INTO sku_leases (sku, owner, expires_at) VALUES (?, ?, ?)",
                (sku, owner, expires_at),
            )
            if cur.rowcount == 0:
                self._conn.rollback()
                raise LeaseUnavailable(f"lease held for {sku}")
        cur.execute(
            "INSERT INTO sku_lease_log (sku, owner, granted_at) VALUES (?, ?, ?)",
            (sku, owner, now),
        )
        token = cur.lastrowid
        self._conn.commit()
        return Lease(sku, owner, expires_at, token)

    def release(self, lease):
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE sku_leases SET expires_at = ? WHERE sku = ? AND owner = ?",
            (self._clock(), lease.sku, lease.owner),
        )
        self._conn.commit()
