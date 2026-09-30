"""Static files (PLAN P4.2): every {% static %} reference must exist.

In production the manifest storage raises on a missing file, turning a harmless 404
into a 500 on the whole page.
"""

import re
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
STATIC_TAG = re.compile(r"""\{%\s*static\s+['"]([^'"]+)['"]\s*%\}""")


class StaticReferencesTests(SimpleTestCase):
    def test_every_static_reference_exists(self):
        missing = []
        for template in ROOT.glob("**/templates/**/*.html"):
            if ".venv" in template.parts:
                continue
            for path in STATIC_TAG.findall(template.read_text(encoding="utf-8")):
                if not finders.find(path):
                    missing.append(f"{template.relative_to(ROOT)}: {path}")
        self.assertEqual(missing, [])


class ProductionCollectstaticTests(SimpleTestCase):
    """The Docker build runs collectstatic with WhiteNoise's manifest storage, which fails on
    any CSS url() that doesn't resolve. That broke the image once (CSS sources were collected
    with relative font paths); run the same thing here."""

    def test_collectstatic_with_manifest_storage(self):
        import io
        import tempfile

        from django.core.management import call_command
        from django.test import override_settings

        with tempfile.TemporaryDirectory() as root:
            storages = {
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {
                    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
                },
            }
            with override_settings(STATIC_ROOT=root, STORAGES=storages):
                call_command("collectstatic", interactive=False, verbosity=0, stdout=io.StringIO())
            collected = {p.name for p in Path(root).rglob("*.css")}
        self.assertIn("app.css", collected)
        self.assertNotIn("01-tokens.css", collected)  # sources stay out of the image
