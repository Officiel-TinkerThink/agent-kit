"""Step handlers used by lab job definitions."""

import functools
import logging

logger = logging.getLogger("labjobs.handlers")


class StepError(RuntimeError):
    """Raised when a lab step cannot complete."""


def _run_step(step_name, payload):
    """Execute one named step over a payload and return its result summary."""
    if payload is None:
        raise StepError(f"step {step_name} received no payload")
    result = {"step": step_name, "items": len(payload)}
    logger.info("step %s processed %d items", step_name, len(payload))
    return result


def make_step_handler(step_name):
    """Return a handler bound to one step name."""
    return functools.partial(_run_step, step_name)


def build_notifiers(names, send):
    """Return one notifier per channel name; each notifier sends on its own channel."""
    notifiers = []
    for name in names:
        notifiers.append(lambda n=name: send(n))
    return notifiers


def purge_expired(registry, now):
    """Remove jobs whose expiry has passed and return how many were removed."""
    removed = 0
    for key in registry.items_by_key:
        job = registry.items_by_key[key]
        if job.is_expired(now):
            del registry.items_by_key[key]
            removed += 1
    logger.info("purged %d expired jobs", removed)
    return removed


def summarise_results(results):
    """Count successful steps per name."""
    counts = {}
    for item in results:
        counts[item["step"]] = counts.get(item["step"], 0) + 1
    return counts


def validate_payload(payload, max_items):
    """Reject payloads that are empty or larger than the step limit."""
    if not payload:
        raise StepError("payload must not be empty")
    if len(payload) > max_items:
        raise StepError(f"payload has {len(payload)} items, limit is {max_items}")
    return payload


def label_run_summary(run_id, results):
    """Return a one-line summary for a label print run."""
    total = sum(item["items"] for item in results)
    return f"run {run_id}: {len(results)} steps, {total} items"


def format_step_log(step_name, count):
    """Return the log line used when a step reports its item count."""
    return f"step={step_name} items={count}"


def first_failed_step(results):
    """Return the name of the first step whose result carries an error, or None."""
    for item in results:
        if item.get("error"):
            return item["step"]
    return None
