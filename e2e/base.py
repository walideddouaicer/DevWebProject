"""Browser end-to-end tests (PLAN P7.5): real Chromium against a live test server.

Run with `make e2e`. They are tagged "e2e" and excluded from `make check`/`make test`.
On failure, a full-page screenshot of every open page is written to e2e/artifacts/.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import override_settings, tag

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")  # Playwright's sync API

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
PASSWORD = "demo12345!"


@tag("e2e")
class BrowserTestCase(StaticLiveServerTestCase):
    """Seeded demo data + one Chromium browser per class; `self.as_(username)` gives a
    logged-in page in its own context (so several people can act side by side)."""

    seed = True

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="e2e-media-")
        cls._settings = override_settings(
            MEDIA_ROOT=f"{cls._media}/public", PRIVATE_MEDIA_ROOT=f"{cls._media}/private"
        )
        cls._settings.enable()
        super().setUpClass()
        from playwright.sync_api import sync_playwright

        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()
        super().tearDownClass()
        cls._settings.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    def setUp(self):
        if self.seed:
            call_command("seed_demo", verbosity=0, stdout=open(os.devnull, "w"))
        self.contexts = []
        self.js_errors = []
        self.expected_console = []  # substrings of console errors a test expects (e.g. a 404)

    def _callTestMethod(self, method):
        try:
            method()
        except BaseException:
            self.save_screenshots()
            raise

    def save_screenshots(self):
        ARTIFACTS.mkdir(exist_ok=True)
        for i, context in enumerate(self.contexts):
            for j, page in enumerate(context.pages):
                name = re.sub(r"\W+", "_", f"{self.id()}_{i}_{j}")
                page.screenshot(path=ARTIFACTS / f"{name}.png", full_page=True)

    def tearDown(self):
        for context in self.contexts:
            context.close()
        unexpected = [e for e in self.js_errors if not any(x in e for x in self.expected_console)]
        self.assertEqual(unexpected, [], "JavaScript errors or CSP violations in the browser")

    # -- helpers
    def page(self):
        context = self.browser.new_context(viewport={"width": 1280, "height": 900})
        context.set_default_timeout(10000)
        self.contexts.append(context)
        page = context.new_page()
        page.on("pageerror", lambda error: self.js_errors.append(str(error)))
        page.on(
            "console",
            lambda m: self.js_errors.append(m.text) if m.type == "error" else None,
        )
        return page

    def url(self, path):
        return f"{self.live_server_url}{path}"

    def login(self, page, username, password=PASSWORD):
        page.goto(self.url("/login/"))
        self.field(page, "Nom d'utilisateur").fill(username)
        self.field(page, "Mot de passe").fill(password)
        page.get_by_role("button", name="Se connecter").click()
        page.wait_for_load_state("networkidle")
        return page

    def as_(self, username):
        return self.login(self.page(), username)

    @staticmethod
    def field(page, label):
        """Form control by its exact label (a trailing required-field asterisk is allowed)."""
        return page.get_by_label(re.compile(rf"^\s*{re.escape(label)}\s*\*?\s*$"))

    @staticmethod
    def choose(select, text):
        """Select the <option> whose text contains ``text``."""
        value = select.locator("option", has_text=text).first.get_attribute("value")
        select.select_option(value)

    def toast(self, page):
        return page.locator(".toast").all_inner_texts()
