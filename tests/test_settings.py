"""Production settings guard rails (PLAN P4.1)."""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from ensa_project_manager.settings import _database_from_url

ROOT = Path(__file__).resolve().parent.parent
GOOD_KEY = "k" * 60


def load_settings(**env):
    """Import settings in a fresh interpreter with the given environment."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "SITE_URL"))}
    clean.update(env)
    return subprocess.run(
        [sys.executable, "-c", "import ensa_project_manager.settings as s; print(s.DEBUG)"],
        cwd=ROOT,
        env=clean,
        capture_output=True,
        text=True,
    )


class ProductionSettingsTests(SimpleTestCase):
    def test_prod_requires_secret_hosts_and_site_url(self):
        result = load_settings(ENVIRONMENT="prod")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)
        result = load_settings(ENVIRONMENT="prod", DJANGO_SECRET_KEY="django-insecure-" + "x" * 60)
        self.assertIn("long random value", result.stderr)
        result = load_settings(ENVIRONMENT="prod", DJANGO_SECRET_KEY=GOOD_KEY)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)
        result = load_settings(
            ENVIRONMENT="prod", DJANGO_SECRET_KEY=GOOD_KEY, DJANGO_ALLOWED_HOSTS="x.ma"
        )
        self.assertIn("SITE_URL", result.stderr)

    def test_complete_prod_config_loads_with_debug_off(self):
        result = load_settings(
            ENVIRONMENT="prod",
            DJANGO_SECRET_KEY=GOOD_KEY,
            DJANGO_ALLOWED_HOSTS="projets.example.ma",
            SITE_URL="https://projets.example.ma",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_database_url_parsing(self):
        db = _database_from_url("postgres://ensa:p%40ss@db:5432/ensa_prod")
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(
            (db["USER"], db["PASSWORD"], db["HOST"], db["PORT"], db["NAME"]),
            ("ensa", "p@ss", "db", "5432", "ensa_prod"),
        )
