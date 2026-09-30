"""Student settings (PLAN P6.6)."""

from django.urls import reverse

from student.models import UserPreferences

from .test_regressions import Fixtures


class SettingsTests(Fixtures):
    def test_notification_preferences_saved(self):
        self.login(self.students[0])
        response = self.client.post(
            reverse("student:account_settings"),
            {"email_notifications": "on", "assignment_reminders": "", "email_digest": "on"},
        )
        self.assertRedirects(response, reverse("student:profile_settings") + "?tab=notifications")
        prefs = UserPreferences.objects.get(user=self.students[0].user)
        self.assertTrue(prefs.email_notifications and prefs.email_digest)
        self.assertFalse(prefs.assignment_reminders or prefs.collaboration_notifications)

    def test_every_settings_tab_renders(self):
        self.login(self.students[0])
        for tab in ["profile", "notifications", "appearance", "account", "bogus"]:
            response = self.client.get(reverse("student:profile_settings"), {"tab": tab})
            self.assertEqual(response.status_code, 200, tab)

    def test_delete_picture_requires_post(self):
        self.login(self.students[0])
        self.assertEqual(
            self.client.get(reverse("student:delete_profile_picture")).status_code, 405
        )
