"""Daily job scheduling for the nightly reagent inventory run."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("lab.schedule")

DEFAULT_ZONE = ZoneInfo("America/New_York")
RUN_HOUR = 2


@dataclass
class DailyJob:
    """A named job with its handler and the instants of its last and next run."""

    name: str
    handler: object
    last_run_utc: datetime | None = None
    next_run_utc: datetime | None = None


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
        job.next_run_utc = run_utc + timedelta(days=1)
        logger.info("job %s ran at %s", job_name, run_utc.isoformat())
        return job.next_run_utc
