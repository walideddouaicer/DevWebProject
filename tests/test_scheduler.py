"""Daily job scheduler (PLAN P4.6)."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, override_settings

from administrator.management.commands.run_scheduler import JOBS, Command, due_jobs

TZ = ZoneInfo("Africa/Casablanca")


class SchedulerTests(SimpleTestCase):
    def test_due_jobs_by_time_and_last_run(self):
        morning = datetime(2026, 10, 5, 8, 30, tzinfo=TZ)
        names = {job.name for job in due_jobs(morning, {})}
        self.assertEqual(names, {"clearsessions", "axes-cleanup", "deadline-reminders"})
        ran_today = {"deadline-reminders": "2026-10-05"}
        self.assertNotIn("deadline-reminders", {j.name for j in due_jobs(morning, ran_today)})
        ran_yesterday = {"deadline-reminders": "2026-10-04"}
        self.assertIn("deadline-reminders", {j.name for j in due_jobs(morning, ran_yesterday)})

    def test_run_due_persists_state_and_never_repeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "state.json"
            with (
                override_settings(SCHEDULER_STATE_FILE=state_file),
                mock.patch("administrator.management.commands.run_scheduler.call_command") as call,
            ):
                evening = datetime(2026, 10, 5, 18, 1, tzinfo=TZ)
                Command().run_due(evening)
                self.assertEqual(call.call_count, len(JOBS))
                Command().run_due(evening)  # restart the same day: nothing re-runs
                self.assertEqual(call.call_count, len(JOBS))
            state = json.loads(state_file.read_text())
            self.assertEqual(set(state.values()), {"2026-10-05"})
