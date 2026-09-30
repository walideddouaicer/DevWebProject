"""Security regressions from the P7.2 review."""

from django.contrib.auth.models import User
from django.core import mail
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import Workbook

from administrator.exports import excel_response, safe_cell
from ensa_project_manager.email_previews import samples
from ensa_project_manager.emails import send_templated_email
from student.views.calendar import _ics_escape


class SecurityTests(SimpleTestCase):
    def test_spreadsheet_formula_injection_is_neutralised(self):
        for value in ('=HYPERLINK("http://x")', "+1", "-2+3", "@SUM(A1)", "\tx", "\rx"):
            with self.subTest(value):
                self.assertEqual(safe_cell(value), "'" + value)
        for value in ("Projet", 12, None, "a=b"):
            self.assertEqual(safe_cell(value), value)

    def test_export_filename_is_quoted_safely(self):
        response = excel_response(Workbook(), 'roster "WEB";401.xlsx')
        header = response["Content-Disposition"]
        self.assertTrue(header.startswith("attachment;"))
        self.assertNotIn('"WEB"', header)

    def test_email_subject_cannot_inject_headers(self):
        send_templated_email(
            "Projet\nBcc: victim@example.com",
            "invitation",
            samples()["invitation"],
            ["a@example.com"],
        )
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Projet Bcc: victim@example.com")
        self.assertEqual(message.bcc, [])

    def test_ics_text_cannot_add_properties(self):
        escaped = _ics_escape("Titre\r\nATTENDEE:mailto:x@y\rSUMMARY:pwn; a,b")
        self.assertNotIn("\r", escaped)
        self.assertNotIn("\n", escaped)
        self.assertIn("\;", escaped)


class OpenRedirectTests(TestCase):
    def test_login_ignores_offsite_next(self):
        User.objects.create_user("u", "u@example.com", "Un-mot-de-passe-42")
        for target in ("https://evil.example.com/", "//evil.example.com/", "/\\evil.example.com"):
            with self.subTest(target):
                response = self.client.post(
                    f"{reverse('login')}?next={target}",
                    {"username": "u", "password": "Un-mot-de-passe-42"},
                )
                self.assertEqual(response.status_code, 302)
                self.assertNotIn("evil", response["Location"])
                self.client.logout()
