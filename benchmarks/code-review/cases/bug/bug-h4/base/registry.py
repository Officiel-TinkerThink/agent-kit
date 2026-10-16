"""In-process registry of scheduled lab jobs, keyed by job key."""

import logging
import threading

logger = logging.getLogger("labjobs.registry")


class RegistryError(RuntimeError):
    """Raised for duplicate keys and capacity overflow."""


class JobRegistry:
    """Holds jobs in a dict owned by the registry; writes are serialised by a lock."""

    def __init__(self, max_jobs=500):
        self.items_by_key = {}
        self._max_jobs = max_jobs
        self._lock = threading.Lock()

    def __len__(self):
        return len(self.items_by_key)

    def register(self, key, job):
        """Store job under key; reject duplicates and overflow."""
        with self._lock:
            if key in self.items_by_key:
                raise RegistryError(f"duplicate job key: {key}")
            if len(self.items_by_key) >= self._max_jobs:
                raise RegistryError(f"registry full ({self._max_jobs} jobs)")
            self.items_by_key[key] = job
            logger.info("registered job %s", key)
            return job

    def get(self, key):
        """Return the job for key, or None when it is not registered."""
        return self.items_by_key.get(key)

    def contains(self, key):
        """Return True when a job is registered under key."""
        return key in self.items_by_key

    def remove(self, key):
        """Remove a job if present; return True when something was removed."""
        with self._lock:
            return self.items_by_key.pop(key, None) is not None

    def keys(self):
        """Return a sorted list of registered keys."""
        return sorted(self.items_by_key)

    def namespaces(self):
        """Return the set of namespaces currently in use."""
        return {job.namespace for job in self.items_by_key.values()}

    def count_by_namespace(self):
        """Return the number of jobs per namespace."""
        counts = {}
        for job in self.items_by_key.values():
            counts[job.namespace] = counts.get(job.namespace, 0) + 1
        return counts
