"""Bounded work queue and worker for lab order capture jobs."""

import logging
import queue
from dataclasses import dataclass

from gateway import GatewayError
from ledger import LedgerError
from settings import QUEUE_MAXSIZE, QUEUE_PUT_TIMEOUT_S, WORKER_POLL_S

logger = logging.getLogger("payments.worker")


class QueueFull(Exception):
    """Raised when the queue stays full past the put timeout (back-pressure)."""


@dataclass(frozen=True)
class CaptureJob:
    """One capture request. The idempotency key is fixed when the job is created."""

    order_id: str
    amount_cents: int
    idempotency_key: str

    def __post_init__(self):
        if self.amount_cents <= 0:
            raise ValueError("amount_cents must be positive")


class CaptureQueue:
    """Bounded FIFO. Producers wait briefly for space, then receive QueueFull."""

    def __init__(self, maxsize=QUEUE_MAXSIZE):
        self._q = queue.Queue(maxsize=maxsize)

    def submit(self, job):
        if not isinstance(job, CaptureJob):
            raise TypeError("job must be a CaptureJob")
        try:
            self._q.put(job, timeout=QUEUE_PUT_TIMEOUT_S)
        except queue.Full as exc:
            raise QueueFull(f"queue full, job for {job.order_id} not accepted") from exc

    def take(self, timeout):
        return self._q.get(timeout=timeout)

    def task_done(self):
        self._q.task_done()

    def pending(self):
        return self._q.qsize()


class CaptureWorker:
    """Processes one job at a time: capture at the provider, then post to the ledger."""

    def __init__(self, capture_queue, gateway, ledger):
        self._queue = capture_queue
        self._gateway = gateway
        self._ledger = ledger
        self.failed_jobs = []

    def process_next(self):
        """Process one job. Return False when no job was available within the poll window."""
        try:
            job = self._queue.take(timeout=WORKER_POLL_S)
        except queue.Empty:
            return False
        try:
            capture_id = self._gateway.capture(job.order_id, job.amount_cents, job.idempotency_key)
            self._ledger.post_capture(job.order_id, job.amount_cents, job.idempotency_key)
            logger.info("job %s completed with capture %s", job.idempotency_key, capture_id)
        except (GatewayError, LedgerError):
            logger.error("job %s for %s not completed", job.idempotency_key, job.order_id, exc_info=True)
            self.failed_jobs.append(job)
        finally:
            self._queue.task_done()
        return True
