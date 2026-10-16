"""Work queue and worker for lab order capture jobs."""

import logging
import queue
from dataclasses import dataclass

from gateway import GatewayError
from settings import WORKER_POLL_S

logger = logging.getLogger("payments.worker")


@dataclass(frozen=True)
class CaptureJob:
    """One capture request."""

    order_id: str
    amount_cents: int
    idempotency_key: str


class CaptureQueue:
    """Unbounded FIFO for capture jobs."""

    def __init__(self):
        self._q = queue.Queue()

    def submit(self, job):
        if not isinstance(job, CaptureJob):
            raise TypeError("job must be a CaptureJob")
        self._q.put(job)

    def take(self, timeout):
        return self._q.get(timeout=timeout)

    def task_done(self):
        self._q.task_done()

    def pending(self):
        return self._q.qsize()


class CaptureWorker:
    """Processes one job at a time: capture at the provider."""

    def __init__(self, capture_queue, gateway):
        self._queue = capture_queue
        self._gateway = gateway
        self.failed_jobs = []

    def process_next(self):
        """Process one job. Return False when no job was available within the poll window."""
        try:
            job = self._queue.take(timeout=WORKER_POLL_S)
        except queue.Empty:
            return False
        try:
            capture_id = self._gateway.capture(job.order_id, job.amount_cents, job.idempotency_key)
            logger.info("job %s completed with capture %s", job.idempotency_key, capture_id)
        except GatewayError:
            logger.error("job %s for %s not completed", job.idempotency_key, job.order_id, exc_info=True)
            self.failed_jobs.append(job)
        finally:
            self._queue.task_done()
        return True
