"""Write, list and prune inventory snapshot archives for the LIMS bridge."""

import hashlib
import logging
import os
import tempfile
from pathlib import Path

from config import BackupSettings

log = logging.getLogger("lims_bridge.backup_store")


class BackupWriteError(RuntimeError):
    """Raised when a snapshot archive cannot be written to the backup root."""


def _checksum(path: Path, algorithm: str) -> str:
    """Return the hex digest of a file, read in fixed-size chunks."""
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(directory: Path) -> None:
    """Flush directory metadata so a completed rename survives a crash."""
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_backup(settings: BackupSettings, payload: bytes, label: str) -> Path:
    """Write payload as a snapshot archive with a checksum sidecar.

    Raises BackupWriteError when the archive or its sidecar cannot be written.
    """
    settings.backup_root.mkdir(parents=True, exist_ok=True)
    target = settings.backup_root / f"{settings.snapshot_prefix}-{label}.tar"
    try:
        with tempfile.NamedTemporaryFile(dir=settings.backup_root, delete=False) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, target)
        _fsync_directory(settings.backup_root)
        digest = _checksum(target, settings.checksum_algorithm)
        sidecar = target.with_name(target.name + ".sha256")
        sidecar.write_text(digest, encoding="utf-8")
    except OSError as exc:
        log.error("snapshot write failed target=%s error=%s", target, exc)
        raise BackupWriteError(f"cannot write snapshot {target.name}") from exc
    log.info("snapshot written target=%s digest=%s", target.name, digest[:12])
    return target


def list_snapshots(settings: BackupSettings) -> list[Path]:
    """Return snapshot archives in the backup root, oldest modification first."""
    if not settings.backup_root.exists():
        return []
    prefix = f"{settings.snapshot_prefix}-"
    archives = [
        path
        for path in settings.backup_root.iterdir()
        if path.name.startswith(prefix) and path.suffix == ".tar"
    ]
    return sorted(archives, key=lambda path: path.stat().st_mtime)


def prune_snapshots(settings: BackupSettings) -> int:
    """Delete the oldest archives beyond retention_count and return how many were removed."""
    snapshots = list_snapshots(settings)
    excess = max(len(snapshots) - settings.retention_count, 0)
    removed = 0
    for path in snapshots[:excess]:
        sidecar = path.with_name(path.name + ".sha256")
        path.unlink()
        if sidecar.exists():
            sidecar.unlink()
        removed += 1
    log.info("pruned snapshots removed=%d retention=%d", removed, settings.retention_count)
    return removed
