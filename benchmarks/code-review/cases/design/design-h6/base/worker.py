"""Background worker that drains accepted instrument events into the audit store."""

import logging
import time

import settings

log = logging.getLogger("intake.worker")


class EventWorker:
    """Takes batches from the event queue and writes them to the audit store."""

    def __init__(self, event_queue, store, batch_size=None):
        self.event_queue = event_queue
        self.store = store
        self.batch_size = batch_size or settings.WORKER_BATCH_SIZE
        self.written_total = 0

    def run_once(self):
        """Process one batch and return the number of events taken from the queue."""
        batch = self.event_queue.take_batch(self.batch_size)
        if not batch:
            return 0
        written = self.store.write_batch(batch)
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

    def run_forever(self, stop_event):
        """Loop until stop_event is set, sleeping when the queue is empty."""
        while not stop_event.is_set():
            if self.run_once() == 0:
                time.sleep(settings.WORKER_IDLE_SLEEP_S)
        log.info("worker stopped with %d events written", self.written_total)
