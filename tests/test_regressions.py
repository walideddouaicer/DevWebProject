"""One regression test per bug in PLAN.md §3 (PLAN P0.7).

Each test asserts the CORRECT behavior. Tests for bugs that aren't fixed yet carry
@expectedFailure; the task that fixes a bug removes the decorator (an unexpected
success makes the suite fail, so a fixed bug can't keep its decorator).
Not covered here: B19 (dependencies, fixed in P0.2), B21 (dead code), B23 (a race that
isn't practical to unit test; fixed by inspection in P2.9).
"""

import shutil
import tempfile
from datetime import timedelta
from unittest import expectedFailure

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.forms import StudentSignupForm
from accounts.models import PendingRegistration
from administrator.models import AdminProfile
from student.models import CollaborationInvitation, Notification, Project, StudentProfile
from teacher.models import (
    DirectStudentAssignment,
    Module,
    ModuleAssignment,
    ModuleEnrollment,
    ProjectAssignment,
    TeacherProfile,
)

PASSWORD = "pass12345!"


class Fixtures(TestCase):
    """Small world: 1 module, 2 teachers (one teaches it), 5 enrolled students, 1 admin."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="regr-media-")
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        def user(name):
            return User.objects.create_user(name, f"{name}@example.com", PASSWORD, first_name=name)

        cls.students = [
            StudentProfile.objects.create(
                user=user(f"s{i}"), student_id=f"S{i}", year_of_study=4, department="GI"
            )
            for i in range(5)
        ]
        cls.teacher = TeacherProfile.objects.create(user=user("teacher"), teacher_id="T1")
        cls.other_teacher = TeacherProfile.objects.create(user=user("other"), teacher_id="T2")
        cls.admin = AdminProfile.objects.create(user=user("admin"), admin_id="A1")
        cls.module = Module.objects.create(name="Web", code="WEB1")
        ModuleAssignment.objects.create(teacher=cls.teacher, module=cls.module)
        for student in cls.students:
            ModuleEnrollment.objects.create(student=student, module=cls.module)

    # -- helpers
    def login(self, profile):
        self.client.force_login(profile.user)

    def assignment(self, **fields):
        defaults = dict(
            teacher=self.teacher,
            module=self.module,
            title="Devoir",
            description="d",
            deadline=timezone.now() + timedelta(days=10),
            assignment_type="direct",
            status="published",
        )
        defaults.update(fields)
        return ProjectAssignment.objects.create(**defaults)

    def project(self, owner, members=(), assignment=None, **fields):
        defaults = dict(
            title="Projet",
            description="d",
            project_type="module",
            student=owner,
            start_date=timezone.localdate(),
            module=self.module,
        )
        if assignment:
            defaults.update(
                assignment_source="teacher_assigned",
                project_assignment=assignment,
                assignment_deadline=assignment.deadline,
            )
        defaults.update(fields)
        project = Project.objects.create(**defaults)
        project.collaborators.add(*members)
        return project


class RegressionTests(Fixtures):
    # B1 ------------------------------------------------------------------
    def test_B1_owner_with_two_collaborators_can_open_project_pages(self):
        s = self.students
        project = self.project(s[0], [s[1], s[2]])
        self.login(s[0])
        for name in ["upload_deliverable", "add_milestone", "project_submit_confirmation"]:
            response = self.client.get(reverse(f"student:{name}", args=[project.id]))
            self.assertLess(response.status_code, 400, name)

    # B2 ------------------------------------------------------------------
    def test_B2_project_form_cannot_attach_collaborators(self):
        s = self.students
        individual = self.assignment(is_team_work=False)
        project = self.project(s[0], assignment=individual)
        self.login(s[0])
        response = self.client.post(
            reverse("student:project_edit", args=[project.id]),
            {
                "title": "Projet",
                "description": "d",
                "project_type": "module",
                "start_date": str(timezone.localdate()),
                "module": self.module.id,
                "collaborators": [s[1].id, s[2].id],
            },
        )
        self.assertEqual(response.status_code, 302)  # the edit itself succeeded
        self.assertEqual(project.collaborators.count(), 0)

    def test_project_end_date_cannot_precede_start_date(self):
        from student.forms import ProjectForm

        form = ProjectForm(
            data={
                "title": "P",
                "description": "d",
                "project_type": "module",
                "start_date": "2026-05-10",
                "end_date": "2026-05-01",
            },
            current_student=self.students[0],
        )
        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    # B3 ------------------------------------------------------------------
    def test_B3_status_url_cannot_bypass_submission_rules(self):
        s = self.students
        team = self.assignment(is_team_work=True, min_team_size=3, max_team_size=3)
        DirectStudentAssignment.objects.create(assignment=team, student=s[0])
        project = self.project(s[0], assignment=team)
        self.login(s[0])
        self.client.post(f"/student/projects/{project.id}/status/submitted/")
        project.refresh_from_db()
        self.assertEqual(project.status, "in_progress")

    # B4 ------------------------------------------------------------------
    def test_B4_unrelated_teacher_cannot_validate_or_reject(self):
        project = self.project(self.students[0], status="submitted", module=None)
        self.login(self.other_teacher)
        for action in ["approve", "reject"]:
            self.client.post(f"/student/projects/{project.id}/{action}/")
            self.client.post(f"/teacher/projects/{project.id}/{action}/")
        project.refresh_from_db()
        self.assertEqual(project.status, "submitted")

    # B5 ------------------------------------------------------------------
    @expectedFailure
    def test_B5_get_does_not_accept_invitation(self):
        s = self.students
        project = self.project(s[0])
        invitation = CollaborationInvitation.objects.create(
            project=project, sender=s[0], recipient=s[1]
        )
        self.login(s[1])
        self.client.get(reverse("student:respond_to_invitation", args=[invitation.id, "accept"]))
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "pending")

    def test_B5_get_does_not_validate_project(self):
        project = self.project(self.students[0], status="submitted")
        self.login(self.teacher)
        self.client.get(reverse("teacher:approve_project", args=[project.id]))
        project.refresh_from_db()
        self.assertEqual(project.status, "submitted")

    # B6 ------------------------------------------------------------------
    @expectedFailure
    def test_B6_active_content_uploads_are_rejected(self):
        project = self.project(self.students[0])
        self.login(self.students[0])
        for name in ["page.html", "logo.svg", "app.js"]:
            upload = SimpleUploadedFile(name, b"<script>alert(1)</script>")
            self.client.post(
                reverse("student:upload_deliverable", args=[project.id]),
                {"file": upload, "file_type": "other", "name": name},
            )
        self.assertEqual(project.deliverables.count(), 0)

    @expectedFailure
    def test_B6_deliverables_are_not_served_from_public_media(self):
        project = self.project(self.students[0])
        self.login(self.students[0])
        self.client.post(
            reverse("student:upload_deliverable", args=[project.id]),
            {
                "file": SimpleUploadedFile("r.pdf", b"%PDF-1.4"),
                "file_type": "report",
                "name": "Rapport",
            },
        )
        deliverable = project.deliverables.get()
        self.assertFalse(deliverable.file.url.startswith(settings.MEDIA_URL))

    # B7 ------------------------------------------------------------------
    @expectedFailure
    def test_B7_teacher_assignment_students_and_teams_pages_render(self):
        direct = self.assignment(target_selection="specific_students", status="draft")
        self.login(self.teacher)
        for name in ["assignment_students", "assignment_teams"]:
            response = self.client.get(reverse(f"teacher:{name}", args=[direct.id]))
            self.assertLess(response.status_code, 400, name)

    @expectedFailure
    def test_B7_admin_and_public_pages_render(self):
        self.login(self.admin)
        for path in [
            "/administrator/users/",
            "/administrator/users/students/",
            "/administrator/users/teachers/",
            "/administrator/statistics/",
            "/explore/",
        ]:
            self.assertLess(self.client.get(path).status_code, 400, path)

    # B8 ------------------------------------------------------------------
    @expectedFailure
    def test_B8_anonymous_assignment_detail_redirects_to_login(self):
        assignment = self.assignment()
        response = self.client.get(reverse("student:assignment_detail", args=[assignment.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    # B9 ------------------------------------------------------------------
    @expectedFailure
    def test_B9_two_teachers_without_id_can_be_approved(self):
        registrations = [
            PendingRegistration.objects.create(
                email=f"t{i}@example.com",
                first_name="T",
                last_name=str(i),
                username=f"newteacher{i}",
                password=make_password("x"),
                role="teacher",
                department="GI",
            )
            for i in range(2)
        ]
        self.login(self.admin)
        for registration in registrations:
            self.client.post(reverse("administrator:approve_registration", args=[registration.id]))
        self.assertEqual(PendingRegistration.objects.filter(is_approved=True).count(), 2)

    # B10 -----------------------------------------------------------------
    @expectedFailure
    def test_B10_progress_of_late_project_does_not_recurse(self):
        project = self.project(
            self.students[0],
            start_date=timezone.localdate() - timedelta(days=30),
            end_date=timezone.localdate() - timedelta(days=1),
        )
        if hasattr(project, "calculate_progress"):
            project.calculate_progress()
            project.is_on_track()

    # B11 -----------------------------------------------------------------
    @expectedFailure
    def test_B11_completion_counts_students_not_projects(self):
        s = self.students
        team = self.assignment(
            is_team_work=True,
            min_team_size=3,
            max_team_size=3,
            target_selection="specific_students",
        )
        for student in s[:3]:
            DirectStudentAssignment.objects.create(assignment=team, student=student)
        self.project(s[0], [s[1], s[2]], assignment=team, status="submitted")
        self.assertEqual(team.get_completion_percentage(), 100)

    # B12 -----------------------------------------------------------------
    @expectedFailure
    def test_B12_creating_a_draft_does_not_notify_students(self):
        self.login(self.teacher)
        deadline = (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M")
        self.client.post(
            reverse("teacher:assignment_create"),
            {
                "title": "Nouveau devoir",
                "description": "Description du devoir",
                "instructions": "",
                "assignment_type": "direct",
                "deadline": deadline,
                "min_team_size": 1,
                "max_team_size": 1,
                "target_selection": "all_students",
                "module": self.module.id,
            },
        )
        self.assertTrue(ProjectAssignment.objects.filter(title="Nouveau devoir").exists())
        self.assertFalse(
            Notification.objects.filter(notification_type="assignment_created").exists()
        )

    # B13 -----------------------------------------------------------------
    @expectedFailure
    def test_B13_late_enrollee_gets_direct_all_students_assignment(self):
        assignment = self.assignment(target_selection="all_students")
        newcomer = StudentProfile.objects.create(
            user=User.objects.create_user("late", "late@example.com", PASSWORD),
            student_id="LATE",
            year_of_study=4,
            department="GI",
        )
        self.login(newcomer)
        self.client.post(reverse("student:join_module"), {"module_code": self.module.code})
        self.assertTrue(
            DirectStudentAssignment.objects.filter(assignment=assignment, student=newcomer).exists()
        )

    # B14 -----------------------------------------------------------------
    def test_B14_submitting_syncs_every_team_member(self):
        s = self.students
        team = self.assignment(
            is_team_work=True,
            min_team_size=2,
            max_team_size=2,
            target_selection="specific_students",
        )
        for student in s[:2]:
            DirectStudentAssignment.objects.create(
                assignment=team, student=student, status="started"
            )
        project = self.project(s[0], [s[1]], assignment=team)
        self.login(s[0])
        self.client.post(reverse("student:project_submit", args=[project.id]))
        statuses = set(
            DirectStudentAssignment.objects.filter(assignment=team).values_list("status", flat=True)
        )
        self.assertEqual(statuses, {"submitted"})

    # B15 -----------------------------------------------------------------
    def test_B15_student_cannot_detach_assignment_project_from_module(self):
        assignment = self.assignment()
        project = self.project(self.students[0], assignment=assignment)
        self.login(self.students[0])
        self.client.post(
            reverse("student:project_edit", args=[project.id]),
            {
                "title": "Projet",
                "description": "d",
                "project_type": "module",
                "start_date": str(timezone.localdate()),
                "module": "",
            },
        )
        project.refresh_from_db()
        self.assertEqual(project.module_id, self.module.id)

    # B16 -----------------------------------------------------------------
    @expectedFailure
    def test_B16_approval_email_has_a_real_login_link(self):
        registration = PendingRegistration.objects.create(
            email="new@example.com",
            first_name="N",
            last_name="S",
            username="newstudent",
            password=make_password("x"),
            role="student",
            student_id="NEW1",
            year_of_study=3,
            department="GI",
        )
        self.login(self.admin)
        self.client.post(reverse("administrator:approve_registration", args=[registration.id]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("[URL_OF_YOUR_SITE]", mail.outbox[0].body)
        self.assertIn("/login/", mail.outbox[0].body)

    # B17 -----------------------------------------------------------------
    @expectedFailure
    def test_B17_signup_rejects_common_passwords(self):
        form = StudentSignupForm(
            data={
                "first_name": "A",
                "last_name": "B",
                "username": "weakpw",
                "email": "weak@example.com",
                "password": "password123",
                "password_confirm": "password123",
                "student_id": "WEAK1",
                "year_of_study": 3,
                "department": "GI",
            }
        )
        self.assertFalse(form.is_valid())

    # B18 -----------------------------------------------------------------
    @expectedFailure
    def test_B18_co_teacher_can_follow_assignment_progress(self):
        assignment = self.assignment()
        ModuleAssignment.objects.create(teacher=self.other_teacher, module=self.module)
        self.login(self.other_teacher)
        response = self.client.get(reverse("teacher:assignment_progress", args=[assignment.id]))
        self.assertEqual(response.status_code, 200)

    # B20 -----------------------------------------------------------------
    @expectedFailure
    def test_B20_locale_matches_audience(self):
        self.assertEqual(settings.TIME_ZONE, "Africa/Casablanca")
        self.assertTrue(settings.LANGUAGE_CODE.startswith("fr"))

    # B22 -----------------------------------------------------------------
    @expectedFailure
    def test_B22_password_reset_exists(self):
        try:
            url = reverse("password_reset")
        except NoReverseMatch:
            self.fail("no password_reset URL")
        self.assertEqual(self.client.get(url).status_code, 200)

    # B24 -----------------------------------------------------------------
    @expectedFailure
    def test_B24_hidden_projects_cannot_be_liked(self):
        project = self.project(
            self.students[0], status="validated", is_public=True, is_hidden_by_admin=True
        )
        self.login(self.students[1])
        response = self.client.post(reverse("public:toggle_project_like", args=[project.id]))
        self.assertEqual(response.status_code, 404)
