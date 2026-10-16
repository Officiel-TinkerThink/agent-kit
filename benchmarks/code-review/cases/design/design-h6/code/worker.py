"""Background worker that drains accepted instrument events into the audit store."""

import logging
import time

import settings
from quota import check_quota

log = logging.getLogger("intake.worker")


class QuotaExceeded(Exception):
    """Raised when a submission would exceed the site's daily event quota."""

    def __init__(self, site_id, incoming):
        super().__init__(f"site {site_id} cannot accept {incoming} more events today")
        self.site_id = site_id
        self.incoming = incoming


class EventWorker:
    """Admits events against the site quota, queues them, and writes batches to the store."""

    def __init__(self, event_queue, store, quota_client, batch_size=None):
        self.event_queue = event_queue
        self.store = store
        self.quota_client = quota_client
        self.batch_size = batch_size or settings.WORKER_BATCH_SIZE
        self.written_total = 0
        self.rejected_total = 0
        self.last_error = None

    def submit(self, site_id, events):
        """Admit a list of events for a site, then enqueue them in order.

        Raises QuotaExceeded when the site's daily quota has no room for the batch.
        Returns the number of events queued.
        """
        if not events:
            return 0
        if not check_quota(site_id, len(events), self.quota_client):
            self.rejected_total += len(events)
            log.warning("quota rejected %d events for site %s", len(events), site_id)
            raise QuotaExceeded(site_id, len(events))
        for event in events:
            self.event_queue.put(event)
        log.info("queued %d events for site %s", len(events), site_id)
        return len(events)

    def run_once(self):
        """Process one batch and return the number of events taken from the queue."""
        batch = self.event_queue.take_batch(self.batch_size)
        if not batch:
            return 0
        written = 0
        try:
            written = self.store.write_batch(batch)
        except Exception as exc:
            self.last_error = str(exc)
            log.error("store write failed for %d events: %s", len(batch), exc)
        self.event_queue.mark_done(batch)
        self.written_total += written
        log.info("stored %d events, total %d", written, self.written_total)
        return len(batch)

    def reset_counters(self):
        """Clear the written counter after a status report has been sent."""
        self.written_total = 0

    def has_written(self):
        """Return True when at least one event has reached the audit store."""
        return self.written_total > 0

    def status(self):
        """Return the written counter and the idle flag for the status page."""
        return {"written_total": self.written_total, "idle": self.is_idle()}

    def __repr__(self):
        return f"EventWorker(batch_size={self.batch_size})"

    def describe(self):
        """Return a short status line for the start-up log."""
        return f"worker batch_size={self.batch_size} written_total={self.written_total}"

    def is_idle(self):
        """Return True when no pending events are waiting for the worker."""
        return self.event_queue.depth() == 0

    def _batch_ids(self, batch):
        """Return the event ids of a batch, for log correlation."""
        return [event.event_id for event in batch]

    def drain_all(self, max_batches=1000):
        """Run batches until the queue is empty or max_batches have been processed."""
        total = 0
        for _ in range(max_batches):
            taken = self.run_once()
            if taken == 0:
                break
            total += taken
        return total

    def run_forever(self, stop_event):
        """Loop until stop_event is set, sleeping when the queue is empty."""
        while not stop_event.is_set():
            if self.run_once() == 0:
                time.sleep(settings.WORKER_IDLE_SLEEP_S)
        log.info("worker stopped with %d events written", self.written_total)

    def stats(self):
        """Return counters for the health endpoint."""
        return {
            "written_total": self.written_total,
            "rejected_total": self.rejected_total,
            "queue_depth": self.event_queue.depth(),
            "in_flight": self.event_queue.in_flight_count(),
            "last_error": self.last_error,
        }
