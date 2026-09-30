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
        css = (ROOT / "assets/css/01-tokens.css").read_text()
        explicit = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S).group(1)
        automatic = re.search(r':not\(\[data-theme="dark"\]\) \{(.*?)\}', css, re.S).group(1)
        normalize = lambda block: re.sub(r"\s+", " ", block).strip()  # noqa: E731
        self.assertEqual(normalize(explicit), normalize(automatic))


class FormWidgetCSPTests(SimpleTestCase):
    """Widget attrs render into HTML: they must not carry inline styles or JS handlers,
    which the enforced CSP blocks (found on the module forms in P7.3)."""

    def test_no_inline_style_or_handlers_in_widget_attrs(self):
        import importlib
        import inspect

        from django import forms

        problems = []
        for module_name in (
            "accounts.forms",
            "administrator.forms",
            "student.forms",
            "teacher.forms",
            "public.forms",
        ):
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError:
                continue
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if not issubclass(cls, forms.BaseForm) or cls.__module__ != module_name:
                    continue
                for field_name, field in cls.base_fields.items():
                    for attr in field.widget.attrs:
                        if attr == "style" or attr.startswith("on"):
                            problems.append(f"{module_name}.{name}.{field_name}: {attr}")
        self.assertFalse(problems, problems)
