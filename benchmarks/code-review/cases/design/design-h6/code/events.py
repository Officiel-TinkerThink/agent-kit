"""In-memory intake queue for accepted instrument events.

Events move from pending to in-flight when a batch is taken. An in-flight
event leaves the queue only when its batch is acknowledged with mark_done(),
or returns to pending when the batch is handed back with restore().
"""

import collections
import logging
import queue
import threading
from dataclasses import dataclass, field

log = logging.getLogger("intake.events")


@dataclass(frozen=True)
class InstrumentEvent:
    """One reading or status message emitted by a lab instrument."""

    event_id: str
    site_id: str
    instrument_id: str
    recorded_at: str
    payload: dict = field(default_factory=dict)


class EventQueue:
    """FIFO queue with at-least-once hand-off between intake and the worker."""

    def __init__(self):
        self._pending = collections.deque()
        self._in_flight = {}
        self._lock = threading.Lock()

    def put(self, event):
        """Append an event to the pending queue."""
        with self._lock:
            self._pending.append(event)

    def take_batch(self, size):
        """Move up to size pending events to in-flight and return them in order."""
        with self._lock:
            count = min(size, len(self._pending))
            batch = [self._pending.popleft() for _ in range(count)]
            for event in batch:
                self._in_flight[event.event_id] = event
            return batch

    def mark_done(self, batch):
        """Acknowledge a batch so its events leave the in-flight set."""
        with self._lock:
            for event in batch:
                self._in_flight.pop(event.event_id, None)

    def restore(self, batch):
        """Return an unacknowledged batch to the front of the pending queue."""
        with self._lock:
            for event in reversed(batch):
                self._in_flight.pop(event.event_id, None)
                self._pending.appendleft(event)

    def depth(self):
        """Return the number of pending events."""
        with self._lock:
            return len(self._pending)

    def in_flight_count(self):
        """Return the number of events taken but not yet acknowledged."""
        with self._lock:
            return len(self._in_flight)


class ReplayBuffer:
    """Bounded buffer for events that must be replayed after a store outage."""

    def __init__(self, maxsize):
        self._items = queue.Queue(maxsize=maxsize)

    def offer(self, event):
        """Return True when the event was buffered, False when the buffer is full."""
        try:
            self._items.put_nowait(event)
        except queue.Full:
            log.warning("replay buffer full, event %s not buffered", event.event_id)
            return False
        return True

    def drain(self):
        """Remove and return every buffered event in arrival order."""
        drained = []
        while True:
            try:
                drained.append(self._items.get_nowait())
            except queue.Empty:
                return drained
