"""Operational endpoints and error pages (PLAN P4.4)."""

from django.test import TestCase, override_settings


class OpsEndpointTests(TestCase):
    def test_healthz_bypasses_host_validation(self):
        response = self.client.get("/healthz", HTTP_HOST="internal-probe")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_robots_and_security_txt(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots["Content-Type"], "text/plain")
        self.assertIn("Disallow: /student/", robots.content.decode())
        security = self.client.get("/.well-known/security.txt").content.decode()
        self.assertIn("Contact: mailto:", security)
        self.assertIn("Expires: ", security)

    def test_favicon(self):
        self.assertEqual(self.client.get("/favicon.ico").status_code, 301)

    @override_settings(DEBUG=False)
    def test_custom_404_page(self):
        response = self.client.get("/nope/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page introuvable", status_code=404)

    def test_500_template_renders_without_context(self):
        from django.template.loader import render_to_string

        html = render_to_string("500.html")
        self.assertIn("Erreur du serveur", html)
