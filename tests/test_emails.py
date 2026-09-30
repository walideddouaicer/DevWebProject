"""Transactional emails: templates, preferences, project decisions (PLAN P6.12)."""

import re
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ensa_project_manager.email_previews import samples
from ensa_project_manager.emails import render_email, send_templated_email
from student.models import Notification, UserPreferences
from teacher.models import DirectStudentAssignment

from .test_regressions import Fixtures


@override_settings(SITE_URL="https://projets.example.com")
class EmailTemplateTests(SimpleTestCase):
    def test_every_email_renders_text_and_html(self):
        for name, context in samples().items():
            with self.subTest(name):
                text, html = render_email(name, context)
                self.assertIsNotNone(html, f"emails/{name}.html is missing")
                self.assertNotIn("{{", text + html)
                self.assertNotIn("{%", text + html)
                self.assertNotRegex(text, r"<(p|div|a|table)\b")  # plain text stays plain
                self.assertIn('<html lang="fr">', html)
                # Every link is absolute (mail clients have no base URL).
                for href in re.findall(r'href="([^"]+)"', html):
                    self.assertTrue(href.startswith("https://projets.example.com"), href)

    def test_html_escapes_user_content(self):
        context = samples()["announcement"] | {"title": "<script>x</script>"}
        _, html = render_email("announcement", context)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_send_attaches_html_alternative(self):
        self.assertTrue(
            send_templated_email("Sujet", "invitation", samples()["invitation"], ["a@example.com"])
        )
        message = mail.outbox[0]
        self.assertIn("Youssef Ouazzani", message.body)
        self.assertEqual(message.alternatives[0][1], "text/html")

    def test_no_recipient_sends_nothing(self):
        self.assertFalse(send_templated_email("S", "invitation", samples()["invitation"], [""]))
        self.assertEqual(mail.outbox, [])


class EmailPreviewRouteTests(SimpleTestCase):
    def test_route_is_debug_only(self):
        # The URLconf is built at import time, with DEBUG=False under tests.
        from django.urls import NoReverseMatch

        with self.assertRaises(NoReverseMatch):
            reverse("email_preview", args=["digest"])


class ProjectDecisionEmailTests(Fixtures):
    def setUp(self):
        self.owner, self.mate = self.students[0], self.students[1]
        self.project_ = self.project(self.owner, [self.mate], status="submitted")

    def recipients(self):
        return sorted(address for m in mail.outbox for address in m.to)

    def test_validate_emails_team_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.project_.validate(by=self.teacher)
        self.assertEqual(self.recipients(), ["s0@example.com", "s1@example.com"])
        self.assertIn("Projet validé", mail.outbox[0].subject)
        self.assertIn(
            reverse("student:project_detail", args=[self.project_.id]), mail.outbox[0].body
        )

    def test_revision_email_carries_teacher_message(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.project_.request_revision(by=self.teacher, message="Ajoutez des tests.")
        self.assertIn("Ajoutez des tests.", mail.outbox[0].body)
        self.assertIn("Ajoutez des tests.", mail.outbox[0].alternatives[0][0])

    def test_preferences_are_respected(self):
        UserPreferences.objects.create(user=self.mate.user, project_notifications=False)
        UserPreferences.objects.create(user=self.owner.user, email_digest=True)
        with self.captureOnCommitCallbacks(execute=True):
            self.project_.reject(by=self.teacher, reason="Hors sujet")
        self.assertEqual(mail.outbox, [])
        # In-app notifications are still created for both.
        self.assertEqual(Notification.objects.filter(project=self.project_).count(), 2)

    def test_submit_by_student_sends_no_email(self):
        project = self.project(self.owner, [self.mate])
        with self.captureOnCommitCallbacks(execute=True):
            project.submit(by=self.owner)
        self.assertEqual(mail.outbox, [])

    def test_grade_and_validate_sends_one_combined_message(self):
        self.login(self.teacher)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("teacher:grade_project", args=[self.project_.id]),
                {"score": "16", "comments": "Très propre.", "validate_project": "on"},
            )
        self.project_.refresh_from_db()
        self.assertEqual(self.project_.status, "validated")
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Projet validé et noté", mail.outbox[0].subject)
        self.assertIn("Très propre.", mail.outbox[0].body)


class ScheduledEmailTests(Fixtures):
    def test_deadline_reminder_email_uses_template(self):
        assignment = self.assignment(deadline=timezone.now() + timedelta(days=3, hours=1))
        DirectStudentAssignment.objects.create(assignment=assignment, student=self.students[0])
        call_command("send_deadline_reminders", stdout=open("/dev/null", "w"))
        self.assertTrue(mail.outbox)
        message = mail.outbox[0]
        self.assertIn(assignment.title, message.subject)
        self.assertIn(reverse("student:assignment_detail", args=[assignment.id]), message.body)
        self.assertEqual(message.alternatives[0][1], "text/html")

    def test_daily_digest(self):
        student = self.students[0]
        UserPreferences.objects.create(user=student.user, email_digest=True)
        for i in range(3):
            Notification.objects.create(
                recipient=student, notification_type="project_update", message=f"Message {i}"
            )
        call_command("send_daily_digest", stdout=open("/dev/null", "w"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["s0@example.com"])
        self.assertIn("3 notifications", mail.outbox[0].subject)
        self.assertIn("Message 2", mail.outbox[0].body)

    def test_password_reset_has_html_version(self):
        self.client.post(reverse("password_reset"), {"email": "s0@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Choisir un nouveau mot de passe", html)
        self.assertRegex(html, r'href="https?://[^"]+/reset/')
