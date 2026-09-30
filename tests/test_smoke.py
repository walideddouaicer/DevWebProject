"""Smoke test (PLAN P0.6): every URL x every role.

Asserts that no page returns a 5xx and that no GET request mutates data. Failures are
compared against KNOWN_FAILURES (each tagged with its bug id from PLAN.md §3):
- a new failure makes the test fail;
- a known failure that no longer happens also fails, so the list gets pruned as bugs are fixed.
"""

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from accounts.models import PendingRegistration
from student.models import (
    CollaborationInvitation,
    Notification,
    Project,
    ProjectDeliverable,
    ProjectMilestone,
    StudentProfile,
    TeammateRequest,
)
from teacher.models import (
    DirectStudentAssignment,
    Module,
    ModuleAssignment,
    ModuleEnrollment,
    ProjectAssignment,
    ProjectOption,
)

ROLES = {
    "anon": None,
    "owner": "etu.youssef",  # owns a 3-person team project
    "student": "etu.anas",  # unrelated student
    "teacher": "prof.alami",  # teaches WEB401
    "teacher_other": "prof.tazi",  # teaches nothing relevant
    "admin": "admin",
}

# (role, url name) -> "5xx" or "mutates". Bug ids refer to PLAN.md §3.
KNOWN_FAILURES = {
    # B7: missing templates
    **{
        (role, "public:explore_projects"): "5xx"
        for role in ["anon", "owner", "student", "teacher", "teacher_other", "admin"]
    },
    ("teacher", "teacher:assignment_teams"): "5xx",
    ("admin", "administrator:users_overview"): "5xx",
    ("admin", "administrator:students_list"): "5xx",
    ("admin", "administrator:teachers_list"): "5xx",
    ("admin", "administrator:statistics"): "5xx",
    # B8: anonymous on requires_module_access views
    ("anon", "student:assignment_detail"): "5xx",
    # B5: state changes on GET
    ("owner", "student:toggle_milestone"): "mutates",
    ("owner", "student:mark_notification_read"): "mutates",
    ("owner", "student:mark_all_notifications_read"): "mutates",
    ("owner", "student:leave_module"): "mutates",
    ("student", "student:leave_module"): "mutates",
    ("student", "student:mark_all_notifications_read"): "mutates",
    ("admin", "administrator:remove_assignment"): "mutates",
    ("admin", "administrator:remove_student_from_module"): "mutates",
}

# URL names never requested (logout ends the session; Django admin is out of scope).
SKIP = {"logout"}


def iter_url_names(patterns=None, namespace=""):
    patterns = get_resolver().url_patterns if patterns is None else patterns
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            if pattern.namespace == "admin" or pattern.app_name == "admin":
                continue
            ns = f"{namespace}{pattern.namespace}:" if pattern.namespace else namespace
            yield from iter_url_names(pattern.url_patterns, ns)
        elif isinstance(pattern, URLPattern) and pattern.name:
            yield f"{namespace}{pattern.name}", list(pattern.pattern.converters)


def fingerprint():
    """Cheap snapshot of mutable state that no GET request may change."""
    return (
        list(Project.objects.order_by("id").values_list("id", "status", "is_public", "module_id")),
        list(Project.collaborators.through.objects.order_by("id").values_list("id")),
        list(CollaborationInvitation.objects.order_by("id").values_list("id", "status")),
        list(ProjectMilestone.objects.order_by("id").values_list("id", "completed")),
        list(Notification.objects.order_by("id").values_list("id", "is_read")),
        list(ModuleEnrollment.objects.order_by("id").values_list("id", "is_active")),
        list(ModuleAssignment.objects.order_by("id").values_list("id", "is_active")),
        list(DirectStudentAssignment.objects.order_by("id").values_list("id", "status")),
        list(TeammateRequest.objects.order_by("id").values_list("id", "is_active")),
        list(ProjectAssignment.objects.order_by("id").values_list("id", "status")),
        list(ProjectDeliverable.objects.order_by("id").values_list("id")),
        list(User.objects.order_by("id").values_list("id", "is_active")),
        list(PendingRegistration.objects.order_by("id").values_list("id", "is_approved")),
    )


class SmokeTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="smoke-media-")
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
        call_command("seed_demo", verbosity=0, stdout=open("/dev/null", "w"))
        youssef = StudentProfile.objects.get(user__username="etu.youssef")
        project = Project.objects.get(student=youssef, project_assignment__module__code="WEB401")
        web = Module.objects.get(code="WEB401")
        assignment = project.project_assignment
        invitation = CollaborationInvitation.objects.filter(status="pending").first()
        cls.kwargs = {
            "project_id": project.id,
            "module_id": web.id,
            "assignment_id": assignment.id,
            "milestone_id": project.milestones.filter(completed=True).first().id,
            "invitation_id": invitation.id,
            "deliverable_id": project.deliverables.first().id,
            "collaborator_id": project.collaborators.first().id,
            "option_id": ProjectOption.objects.filter(assignment=assignment, current_teams=0)
            .first()
            .id,
            "notification_id": Notification.objects.filter(recipient=youssef).first().id
            if Notification.objects.filter(recipient=youssef).exists()
            else Notification.objects.first().id,
            "registration_id": PendingRegistration.objects.first().id,
            "student_id": ModuleEnrollment.objects.filter(module=web, is_active=True)
            .first()
            .student_id,
            "user_id": User.objects.get(username="etu.anas").id,
            "new_status": "submitted",
            "response": "accept",
        }
        # Routes whose kwarg name is ambiguous get their own values
        cls.overrides = {
            "administrator:remove_assignment": {
                "assignment_id": ModuleAssignment.objects.filter(module=web).first().id
            },
        }
        # A notification for the owner so mark-read endpoints have something to act on
        Notification.objects.create(
            recipient=youssef, notification_type="project_update", message="Test"
        )
        cls.kwargs["notification_id"] = Notification.objects.filter(recipient=youssef).last().id

    def test_every_url_every_role(self):
        routes = []
        for name, params in iter_url_names():
            if name in SKIP:
                continue
            missing = [p for p in params if p not in self.kwargs]
            self.assertFalse(missing, f"smoke test has no value for {missing} in {name}")
            values = {**self.kwargs, **self.overrides.get(name, {})}
            routes.append((name, reverse(name, kwargs={p: values[p] for p in params})))

        failures = {}
        self.client.raise_request_exception = False
        for role, username in ROLES.items():
            self.client.logout()
            if username:
                self.client.force_login(User.objects.get(username=username))
            for name, path in routes:
                with transaction.atomic():
                    before = fingerprint()
                    with transaction.atomic():  # savepoint: a DB error must not poison `after`
                        response = self.client.get(path)
                    if response.status_code >= 500:
                        failures[(role, name)] = "5xx"
                    elif before != fingerprint():
                        failures[(role, name)] = "mutates"
                    transaction.set_rollback(True)

        new = {k: v for k, v in failures.items() if KNOWN_FAILURES.get(k) != v}
        fixed = {k: v for k, v in KNOWN_FAILURES.items() if failures.get(k) != v}
        message = []
        if new:
            message.append(
                "NEW failures:\n" + "\n".join(f"  {k}: {v}" for k, v in sorted(new.items()))
            )
        if fixed:
            message.append(
                "No longer failing — remove from KNOWN_FAILURES:\n"
                + "\n".join(f"  {k}: {v}" for k, v in sorted(fixed.items()))
            )
        self.assertFalse(message, "\n".join(message))
