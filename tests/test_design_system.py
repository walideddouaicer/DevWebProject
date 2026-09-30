"""Design system integrity (PLAN P5.4)."""

import re
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent


class DesignSystemTests(SimpleTestCase):
    def test_app_css_is_built_from_sources(self):
        result = subprocess.run([sys.executable, "scripts/build_css.py", "--check"], cwd=ROOT)
        self.assertEqual(result.returncode, 0, "run scripts/build_css.py")

    def test_tokens_meet_wcag_contrast(self):
        result = subprocess.run(
            [sys.executable, "scripts/contrast_check.py"], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_dark_token_blocks_are_identical(self):
        css = (ROOT / "static/css/src/01-tokens.css").read_text()
        explicit = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S).group(1)
        automatic = re.search(r':not\(\[data-theme="dark"\]\) \{(.*?)\}', css, re.S).group(1)
        normalize = lambda block: re.sub(r"\s+", " ", block).strip()  # noqa: E731
        self.assertEqual(normalize(explicit), normalize(automatic))
