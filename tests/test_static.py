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
