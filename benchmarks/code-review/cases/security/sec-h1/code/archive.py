"""Unpack zip archives that accompany a batch record into the batch staging directory."""

import logging
import os
import zipfile

import yaml

logger = logging.getLogger("lab.archive")

MAX_MEMBERS = 500
CHUNK_SIZE = 64 * 1024


def read_manifest(archive_path):
    """Read manifest.yaml from the archive and return it as a mapping."""
    with zipfile.ZipFile(archive_path) as archive:
        with archive.open("manifest.yaml") as handle:
            manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a mapping")
    return manifest


def validate_member_count(archive):
    """Reject archives with more members than the configured limit."""
    count = len(archive.infolist())
    if count > MAX_MEMBERS:
        raise ValueError("archive has %d members, limit is %d" % (count, MAX_MEMBERS))
    return count


def unpack_batch_archive(archive_path, dest):
    """Extract every member of the archive into dest, reporting progress."""
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        validate_member_count(archive)
        for index, member in enumerate(members, start=1):
            if member.is_dir():
                continue
            target = os.path.join(dest, member.filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(member) as source, open(target, "wb") as sink:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    sink.write(chunk)
            if index % 50 == 0:
                logger.info("unpacked %d of %d members", index, len(members))
    logger.info("unpacked %d members into %s", len(members), dest)
    return len(members)


def list_staged_files(dest):
    """Return the relative paths of all files currently staged under dest."""
    names = []
    for root, _dirs, files in os.walk(dest):
        for name in files:
            names.append(os.path.relpath(os.path.join(root, name), dest))
    return sorted(names)


def stage_size_bytes(dest):
    """Return the total size in bytes of the files staged under dest."""
    total = 0
    for name in list_staged_files(dest):
        total += os.path.getsize(os.path.join(dest, name))
    return total
