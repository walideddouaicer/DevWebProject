"""Block until the database accepts connections (container start-up, PLAN P4.6)."""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Attend que la base de données soit joignable."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=60)

    def handle(self, *args, **options):
        deadline = time.monotonic() + options["timeout"]
        while True:
            try:
                connection.ensure_connection()
                self.stdout.write("Database ready.")
                return
            except OperationalError:
                if time.monotonic() > deadline:
                    raise CommandError("Database still unreachable, giving up.")
                time.sleep(1)
