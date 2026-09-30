"""Operations commands (PLAN P4.8)."""

import io

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.permissions import get_role


class CreateAdminTests(TestCase):
    def test_creates_admin_with_generated_password_shown_once(self):
        out = io.StringIO()
        call_command("createadmin", username="chef", email="chef@example.com", stdout=out)
        user = User.objects.get(username="chef")
        password = out.getvalue().split("une seule fois) : ")[1].strip()
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertEqual(get_role(user), "admin")
        # running again is safe and doesn't change the password
        call_command("createadmin", username="chef", email="chef@example.com", stdout=io.StringIO())
        user.refresh_from_db()
        self.assertTrue(user.check_password(password))

    def test_rejects_weak_password(self):
        with self.assertRaises(CommandError):
            call_command(
                "createadmin",
                username="x",
                email="x@example.com",
                password="123",
                stdout=io.StringIO(),
            )


class CheckEmailTests(TestCase):
    def test_sends_test_message(self):
        call_command("check_email", "ops@example.com", stdout=io.StringIO())
        self.assertEqual(mail.outbox[0].to, ["ops@example.com"])


class ApprovalTests(TestCase):
    def test_administrator_registration_gets_admin_profile(self):
        from django.contrib.auth.hashers import make_password

        from accounts.models import PendingRegistration

        approver = User.objects.create_user("boss", "b@example.com", "x")
        registration = PendingRegistration.objects.create(
            email="new-admin@example.com",
            first_name="A",
            last_name="B",
            username="newadmin",
            password=make_password("x"),
            role="administrator",
        )
        user = registration.approve(by=approver)
        self.assertEqual(get_role(user), "admin")
