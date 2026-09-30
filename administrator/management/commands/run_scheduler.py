"""Long-running scheduler for the daily jobs (PLAN P4.6).

    python manage.py run_scheduler            # runs forever (the `scheduler` container)
    python manage.py run_scheduler --once     # run whatever is due now, then exit

Each job runs at most once per local day. The last run date is persisted in a small JSON
file (SCHEDULER_STATE_FILE), so a restart neither skips nor repeats a job: if the
container was down at 08:00 it catches up when it comes back, the same day.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    name: str
    hour: int
    minute: int
    command: str
    args: tuple = ()


JOBS = [
    Job("clearsessions", 3, 0, "clearsessions"),
    Job("axes-cleanup", 3, 15, "axes_reset_failure_logs", ("--age", "30")),
    Job("deadline-reminders", 8, 0, "send_deadline_reminders"),
    Job("daily-digest", 18, 0, "send_daily_digest"),
]


def due_jobs(now: datetime, last_runs: dict[str, str], jobs=JOBS):
    """Jobs whose time has passed today and that haven't run today."""
    today = now.date().isoformat()
    return [
        job
        for job in jobs
        if (now.hour, now.minute) >= (job.hour, job.minute) and last_runs.get(job.name) != today
    ]


def state_path():
    return Path(getattr(settings, "SCHEDULER_STATE_FILE", settings.BASE_DIR / ".scheduler.json"))


def load_state():
    try:
        return json.loads(state_path().read_text())
    except (FileNotFoundError, ValueError):
        return {}


def save_state(state):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)


class Command(BaseCommand):
    help = "Exécute les tâches quotidiennes (rappels, digest, nettoyage) à heure fixe."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run due jobs once and exit.")
        parser.add_argument("--interval", type=int, default=30, help="Polling interval (s).")

    def handle(self, *args, **options):
        logger.info("Scheduler started with %d jobs", len(JOBS))
        while True:
            self.run_due(timezone.localtime())
            if options["once"]:
                return
            time.sleep(options["interval"])

    def run_due(self, now):
        state = load_state()
        for job in due_jobs(now, state):
            logger.info("Running %s", job.name)
            try:
                call_command(job.command, *job.args)
            except Exception:
                logger.exception("Job %s failed", job.name)
            # Mark as run even on failure: a broken job must not retry every 30 s.
            state[job.name] = date.isoformat(now.date())
            save_state(state)
