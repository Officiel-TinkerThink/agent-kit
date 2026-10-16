"""Job model and factory for lab automation tasks.

A job couples a unique key with a handler callable, the namespace it belongs
to, an optional expiry instant and a list of tags used for lookup.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, List, Optional

from registry import JobRegistry

logger = logging.getLogger("labjobs.jobs")


class JobError(RuntimeError):
    """Raised when a job handler fails during a run."""


@dataclass
class Job:
    """A registered unit of lab work."""

    key: str
    handler: Callable[..., Any]
    namespace: str = "default"
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    def is_expired(self, now):
        """Return True when the expiry instant is at or before now."""
        return self.expires_at is not None and self.expires_at <= now


def add_job(registry: JobRegistry, key, handler, tags=[], namespace="default", expires_at=None):
    """Create a job with its namespace tag, register it, and return it."""
    if not key:
        raise ValueError("job key must be non-empty")
    if expires_at is not None and expires_at.tzinfo is None:
        raise ValueError("expires_at must be timezone-aware")
    tags.append(f"ns:{namespace}")
    job = Job(key=key, handler=handler, namespace=namespace, expires_at=expires_at, tags=tags)
    logger.info("job %s created in namespace %s", key, namespace)
    return registry.register(key, job)


def make_callbacks(names, runner):
    """Return one callback per step name; each callback runs its own step."""
    callbacks = []
    for name in names:
        callbacks.append(lambda: runner(name))
    return callbacks


def describe_job(job):
    """Return a plain mapping of the job fields for reports."""
    return {
        "key": job.key,
        "namespace": job.namespace,
        "tags": list(job.tags),
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
    }


def run_job(job, *args, **kwargs):
    """Invoke the job handler and wrap any failure in JobError."""
    try:
        return job.handler(*args, **kwargs)
    except Exception as exc:
        logger.exception("job %s failed", job.key)
        raise JobError(f"job {job.key} failed: {exc}") from exc
