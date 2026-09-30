"""Signup, module membership, admin module/moderation actions, upload validators (PLAN P7.1)."""

import io
from datetime import timedelta

from django import forms
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import PendingRegistration
from student.models import Notification, ProjectReport
from student.validators import validate_deliverable_file, validate_image_file
from teacher.models import Module, ModuleAssignment, ModuleEnrollment, ProjectAssignment

from .test_regressions import Fixtures


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, "PNG")
    return buffer.getvalue()


class ValidatorTests(SimpleTestCase):
    def test_deliverable_allowlist_and_size(self):
        validate_deliverable_file(SimpleUploadedFile("rapport.PDF", b"%PDF"))
        for name in ("page.html", "script.js", "logo.svg", "noext"):
            with self.subTest(name), self.assertRaises(forms.ValidationError):
                validate_deliverable_file(SimpleUploadedFile(name, b"x"))
        big = SimpleUploadedFile("big.zip", b"x")
        big.size = 11 * 1024 * 1024
        with self.assertRaisesMessage(forms.ValidationError, "10 Mo"):
            validate_deliverable_file(big)

    def test_image_must_really_be_an_image(self):
        validate_image_file(SimpleUploadedFile("a.png", png_bytes(), content_type="image/png"))
        cases = {
            "wrong extension": SimpleUploadedFile("a.svg", b"<svg/>", content_type="image/svg"),
            "not an image type": SimpleUploadedFile("a.png", b"x", content_type="text/plain"),
            "fake png": SimpleUploadedFile("a.png", b"not a png", content_type="image/png"),
        }
        for label, upload in cases.items():
            with self.subTest(label), self.assertRaises(forms.ValidationError):
                validate_image_file(upload)
        big = SimpleUploadedFile("a.png", png_bytes(), content_type="image/png")
        big.size = 6 * 1024 * 1024
        with self.assertRaises(forms.ValidationError):
            validate_image_file(big)


class SignupTests(TestCase):
    data = {
        "first_name": "Salma",
        "last_name": "Chraibi",
        "username": "salma",
        "email": "Salma@Example.com",
        "password": "Un-mot-de-passe-solide-42",
        "password_confirm": "Un-mot-de-passe-solide-42",
        "student_id": "E2026",
        "year_of_study": "3",
        "department": "GI",
    }

    def test_student_signup_creates_pending_registration_and_emails(self):
        response = self.client.post(reverse("accounts:student_signup"), self.data)
        self.assertRedirects(response, reverse("public:homepage"))
        registration = PendingRegistration.objects.get()
        self.assertEqual(registration.email, "salma@example.com")
        self.assertFalse(User.objects.filter(username="salma").exists())
        self.assertEqual(mail.outbox[0].to, ["salma@example.com"])

    def test_duplicates_are_case_insensitive(self):
        self.client.post(reverse("accounts:student_signup"), self.data)
        again = {**self.data, "username": "SALMA", "email": "SALMA@example.com", "student_id": "X"}
        response = self.client.post(reverse("accounts:student_signup"), again)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "en attente")
        self.assertEqual(PendingRegistration.objects.count(), 1)

    def test_teacher_signup_form_renders(self):
        response = self.client.get(reverse("accounts:teacher_signup"))
        self.assertContains(response, "Inscription enseignant")

    def test_admin_signup_route_is_gone(self):
        self.assertEqual(self.client.get("/accounts/signup/admin/").status_code, 404)


class StudentModuleTests(Fixtures):
    def setUp(self):
        self.student = self.students[0]
        self.other = Module.objects.create(name="IA", code="IA9")
        self.login(self.student)

    def join(self, code):
        return self.client.post(reverse("student:join_module"), {"module_code": code}, follow=True)

    def test_join_by_code_attaches_published_assignments(self):
        ProjectAssignment.objects.create(
            teacher=self.teacher,
            module=self.other,
            title="TP",
            description="d",
            deadline=timezone.now() + timedelta(days=30),
            assignment_type="choice",
            status="published",
        )
        response = self.join("ia9")
        self.assertContains(response, "IA")
        self.assertTrue(
            ModuleEnrollment.objects.filter(
                student=self.student, module=self.other, is_active=True
            ).exists()
        )

    def test_unknown_or_inactive_code(self):
        self.other.is_active = False
        self.other.save()
        self.assertContains(self.join("IA9"), "Aucun module")
        self.assertContains(self.join("NOPE"), "Aucun module")

    def test_leave_then_rejoin(self):
        self.client.post(reverse("student:leave_module", args=[self.module.id]))
        enrollment = ModuleEnrollment.objects.get(student=self.student, module=self.module)
        self.assertFalse(enrollment.is_active)
        self.assertContains(self.join(self.module.code), "à nouveau")
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.is_active)

    def test_leave_module_not_enrolled(self):
        response = self.client.post(
            reverse("student:leave_module", args=[self.other.id]), follow=True
        )
        self.assertContains(response, "pas inscrit")


class AdminModuleActionTests(Fixtures):
    def setUp(self):
        self.login(self.admin)

    def test_assign_reassign_and_remove_teacher(self):
        url = reverse("administrator:assign_teacher_to_module")
        self.client.post(url, {"teacher_id": self.other_teacher.id, "module_id": self.module.id})
        assignment = ModuleAssignment.objects.get(teacher=self.other_teacher)
        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.assigned_by, self.admin.user)

        self.client.post(reverse("administrator:remove_assignment", args=[assignment.id]))
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

        self.client.post(url, {"teacher_id": self.other_teacher.id, "module_id": self.module.id})
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)
        self.assertEqual(ModuleAssignment.objects.filter(teacher=self.other_teacher).count(), 1)

    def test_assign_with_missing_or_unknown_ids(self):
        url = reverse("administrator:assign_teacher_to_module")
        for data in ({}, {"teacher_id": 999, "module_id": self.module.id}):
            with self.subTest(data):
                response = self.client.post(url, data, follow=True)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(ModuleAssignment.objects.count(), 1)

    def test_unenroll_student_html_and_ajax(self):
        student = self.students[0]
        url = reverse("administrator:remove_student_from_module", args=[self.module.id, student.id])
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json()["success"], True)
        response = self.client.post(url)
        self.assertRedirects(
            response, reverse("administrator:module_detail", args=[self.module.id])
        )
        self.assertFalse(ModuleEnrollment.objects.get(student=student).is_active)


class ModerationTests(Fixtures):
    def setUp(self):
        self.owner = self.students[0]
        self.project_ = self.project(
            self.owner, status="validated", is_public=True, is_reported=True, report_count=2
        )
        for reporter in self.students[1:3]:
            ProjectReport.objects.create(
                project=self.project_, reporter=reporter.user, reason="spam", description="x"
            )
        self.login(self.admin)
        self.url = reverse("administrator:moderate_project", args=[self.project_.id])

    def moderate(self, action, notes=""):
        self.client.post(self.url, {"action": action, "admin_notes": notes})
        self.project_.refresh_from_db()

    def test_hide_notifies_owner_with_reason_then_unhide(self):
        self.moderate("hide", "Contenu copié")
        self.assertTrue(self.project_.is_hidden_by_admin)
        self.assertFalse(self.project_.is_public)
        self.assertFalse(self.project_.reports.filter(is_reviewed=False).exists())
        self.assertIn("Contenu copié", Notification.objects.get(recipient=self.owner).message)
        self.moderate("unhide")
        self.assertFalse(self.project_.is_hidden_by_admin)
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 2)

    def test_dismiss_keeps_project_public(self):
        self.moderate("dismiss")
        self.assertTrue(self.project_.is_public)
        self.assertFalse(self.project_.is_reported)
        self.assertFalse(self.project_.reports.filter(is_reviewed=False).exists())

    def test_invalid_action_and_get_change_nothing(self):
        self.moderate("delete")
        self.client.get(self.url)
        self.project_.refresh_from_db()
        self.assertTrue(self.project_.is_public)
        self.assertTrue(self.project_.is_reported)

    def test_moderation_queue_tabs(self):
        for show in ("pending", "hidden", "all"):
            with self.subTest(show):
                response = self.client.get(
                    reverse("administrator:reports_moderation"), {"show": show}
                )
                self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("administrator:reports_moderation"))
        self.assertContains(response, self.project_.title)
