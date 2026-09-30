"""Login throttling and logout (PLAN P1.9)."""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
class LockoutTests(TestCase):
    def setUp(self):
        User.objects.create_user("victim", "v@example.com", "correct-horse-9")

    def attempt(self, password):
        return self.client.post(
            reverse("login"), {"username": "victim", "password": password}, REMOTE_ADDR="10.0.0.1"
        )

    def test_lockout_after_repeated_failures(self):
        for _ in range(3):
            self.attempt("wrong")
        response = self.attempt("correct-horse-9")  # right password, but locked out
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Trop de tentatives", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_before_limit_logs_in(self):
        self.attempt("wrong")
        response = self.attempt("correct-horse-9")
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)


class LogoutTests(TestCase):
    def test_logout_requires_post(self):
        user = User.objects.create_user("u", "u@example.com", "pw-123456789")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
