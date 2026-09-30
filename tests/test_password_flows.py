"""Password reset and change (PLAN P2.8)."""

import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse


class PasswordFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "prof.x", "prof.x@example.com", "Ancien-mdp-2026", first_name="Karim"
        )

    def test_reset_flow_end_to_end(self):
        login_page = self.client.get(reverse("login"))
        self.assertContains(login_page, reverse("password_reset"))

        response = self.client.post(reverse("password_reset"), {"email": "prof.x@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Bonjour Karim", body)
        link = re.search(r"https?://[^/\s]+(/reset/\S+/)", body).group(1)

        form_page = self.client.get(link, follow=True)
        self.assertContains(form_page, "Choisissez un nouveau mot de passe")
        response = self.client.post(
            form_page.redirect_chain[-1][0],
            {"new_password1": "Nouveau-mdp-2026!", "new_password2": "Nouveau-mdp-2026!"},
        )
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Nouveau-mdp-2026!"))

    def test_unknown_email_sends_nothing_but_looks_the_same(self):
        response = self.client.post(reverse("password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_any_logged_in_user_can_change_password(self):
        self.assertEqual(self.client.get(reverse("password_change")).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "Ancien-mdp-2026",
                "new_password1": "Encore-nouveau-99",
                "new_password2": "Encore-nouveau-99",
            },
        )
        self.assertRedirects(response, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Encore-nouveau-99"))
