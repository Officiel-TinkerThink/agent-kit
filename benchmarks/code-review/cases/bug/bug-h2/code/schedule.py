"""Daily job scheduling for the nightly reagent inventory run."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger("lab.schedule")

DEFAULT_ZONE = ZoneInfo("America/New_York")
RUN_HOUR = 2
RUN_INTERVAL_HOURS = 24


@dataclass
class DailyJob:
    """A named job with its handler and the instants of its last and next run."""

    name: str
    handler: object
    last_run_utc: datetime | None = None
    next_run_utc: datetime | None = None


def first_run_after(now_utc, zone=DEFAULT_ZONE):
    """Return the first RUN_HOUR local run strictly after now_utc, as aware UTC."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    local_now = now_utc.astimezone(zone)
    candidate = local_now.replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= local_now:
        candidate = candidate + timedelta(days=1)
    logger.info("first run after %s is %s", now_utc.isoformat(), candidate.isoformat())
    return candidate.astimezone(timezone.utc)


def next_daily_run(last_run_utc, zone=DEFAULT_ZONE):
    """Return the aware UTC instant of the run that follows last_run_utc."""
    if last_run_utc.tzinfo is None:
        raise ValueError("last_run_utc must be timezone-aware")
    candidate = last_run_utc + timedelta(hours=RUN_INTERVAL_HOURS)
    logger.info(
        "next run after %s is %s local",
        last_run_utc.isoformat(),
        candidate.astimezone(zone).isoformat(),
    )
    return candidate


def seconds_until(run_utc, now_utc):
    """Return the seconds from now_utc until run_utc; negative when overdue."""
    return (run_utc - now_utc).total_seconds()


@dataclass
class JobScheduler:
    """Keeps registered jobs and reports the ones that are due."""

    zone: ZoneInfo = DEFAULT_ZONE
    jobs: dict = field(default_factory=dict)

    def register(self, job, first_run_utc):
        """Add a job whose first run is at first_run_utc (aware UTC)."""
        if job.name in self.jobs:
            raise KeyError(f"job already registered: {job.name}")
        if first_run_utc.tzinfo is None:
            raise ValueError("first_run_utc must be timezone-aware")
        job.next_run_utc = first_run_utc
        self.jobs[job.name] = job
        logger.info("registered job %s first run %s", job.name, first_run_utc.isoformat())

    def due_jobs(self, now_utc):
        """Return the jobs whose next run instant is at or before now_utc."""
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware")
        return [
            job
            for job in self.jobs.values()
            if job.next_run_utc is not None and job.next_run_utc <= now_utc
        ]

    def mark_ran(self, job_name, run_utc):
        """Record a completed run and schedule the following one."""
        job = self.jobs[job_name]
        job.last_run_utc = run_utc
        job.next_run_utc = next_daily_run(run_utc, self.zone)
        logger.info("job %s ran at %s", job_name, run_utc.isoformat())
        return job.next_run_utc
