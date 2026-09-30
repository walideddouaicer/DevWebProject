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
    DeliverableComment,
    Notification,
    Project,
    ProjectComment,
    ProjectDeliverable,
    ProjectLike,
    ProjectMilestone,
    ProjectReport,
    PublicProjectComment,
    StudentProfile,
    TeammateRequest,
)
from teacher.models import (
    DirectStudentAssignment,
    Module,
    ModuleAnnouncement,
    ModuleAssignment,
    ModuleEnrollment,
    ProjectAssignment,
    ProjectEvaluation,
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
KNOWN_FAILURES = {}

# Routes an outsider may legitimately GET with someone else's id (e.g. a module they can join).
OUTSIDER_ALLOWED = set()

# Legacy RedirectView aliases: they redirect to the canonical route, which does the role check.
ALIASES = {
    "administrator:users_overview",
    "administrator:students_list",
    "administrator:teachers_list",
}

# Views shared across roles on purpose (the view checks access to the object itself;
# private files answer 404 to everyone else, anonymous users included).
SHARED = {"student:deliverable_download"}

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


def _counted():
    return (
        ProjectComment,
        DeliverableComment,
        PublicProjectComment,
        ProjectLike,
        ProjectReport,
        ModuleAnnouncement,
    )


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
        [m.objects.count() for m in _counted()],
        list(ProjectEvaluation.objects.order_by("id").values_list("id", "score")),
        list(Project.objects.order_by("id").values_list("id", "title", "is_hidden_by_admin")),
        list(ProjectMilestone.objects.order_by("id").values_list("id", "title")),
        list(Module.objects.order_by("id").values_list("id", "name", "is_active")),
        list(ProjectOption.objects.order_by("id").values_list("id", "title")),
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
            "uidb64": "MQ",  # an invalid reset link: renders the "lien invalide" page
            "token": "set-password",
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

    def crawl(self):
        """GET every route as every role, once per class: (failures, {(role, name): response})."""
        cache = type(self).__dict__.get("_crawl")
        if cache is not None:
            return cache
        routes = []
        for name, params in iter_url_names():
            if name in SKIP:
                continue
            missing = [p for p in params if p not in self.kwargs]
            self.assertFalse(missing, f"smoke test has no value for {missing} in {name}")
            values = {**self.kwargs, **self.overrides.get(name, {})}
            routes.append((name, reverse(name, kwargs={p: values[p] for p in params})))

        failures, responses = {}, {}
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
                    responses[(role, name)] = (response.status_code, response.get("Location", ""))
                    if response.status_code >= 500:
                        failures[(role, name)] = "5xx"
                    elif before != fingerprint():
                        failures[(role, name)] = "mutates"
                    transaction.set_rollback(True)
        type(self)._crawl = (failures, responses)
        return failures, responses

    def test_permission_matrix(self):
        """Role areas: anon → login, wrong role → 403; outsiders never get a 200."""
        _, responses = self.crawl()
        area_role = {
            "student": {"owner", "student"},
            "teacher": {"teacher", "teacher_other"},
            "administrator": {"admin"},
        }
        problems = []
        for (role, name), (status, location) in sorted(responses.items()):
            area = name.split(":")[0]
            if area not in area_role or status == 405 or name in ALIASES:
                continue
            if name in SHARED:
                continue
            if role == "anon":
                if status != 302 or "/login/" not in location:
                    problems.append(f"{role:14} {name}: {status} (expected login redirect)")
            elif role not in area_role[area]:
                if status != 403:
                    problems.append(f"{role:14} {name}: {status} (expected 403)")
        # Outsiders on resources that belong to someone else
        scoped = {
            "student": ("project_id", "milestone_id", "deliverable_id", "collaborator_id"),
            "teacher_other": (
                "project_id",
                "module_id",
                "assignment_id",
                "option_id",
                "deliverable_id",
                "student_id",
            ),
        }
        for role, params in scoped.items():
            area = "student" if role == "student" else "teacher"
            for name, route_params in iter_url_names():
                if not name.startswith(f"{area}:") or not set(route_params) & set(params):
                    continue
                status, _ = responses.get((role, name), (None, ""))
                if status == 200 and name not in OUTSIDER_ALLOWED:
                    problems.append(f"{role:14} {name}: 200 on someone else's resource")
        self.assertFalse(problems, "\n" + "\n".join(problems))

    def test_outsiders_cannot_mutate_by_post(self):
        """IDOR on writes: an unrelated student / teacher POSTs a plausible payload to every
        route that takes an object id; nothing may change (public-site actions excepted)."""
        project = Project.objects.get(pk=self.kwargs["project_id"])
        payload = {
            "content": "Commentaire",
            "title": "Pirate",
            "description": "d",
            "name": "x",
            "action": "hide",
            "admin_notes": "x",
            "response": "accept",
            "score": "20",
            "comments": "x",
            "validate_project": "on",
            "message": "x",
            "reason": "spam",
            "collaborator": self.kwargs["user_id"],
            "due_date": "2030-01-01",
            "module_code": project.module.code if project.module else "X",
            "student_ids": [self.kwargs["student_id"]],
            "project_ids": [project.id],
            "status": "validated",
            "is_active": "on",
            "code": "PWN1",
        }
        # Actions on the requester's own data that happen to take a shared object's id
        own_actions = {"student:leave_module"}  # leaves *their own* enrollment
        public_actions = {
            "public:toggle_project_like",
            "public:add_project_comment",
            "public:add_public_comment",
            "public:report_project",
        }
        # Likes/comments/reports are legitimate on showcase projects only; on a private
        # project they must 404 like everything else.
        skipped = own_actions | (public_actions if project.is_public else set())
        problems = []
        self.client.raise_request_exception = False
        for role in ("student", "teacher_other"):
            self.client.force_login(User.objects.get(username=ROLES[role]))
            for name, params in iter_url_names():
                if not params or name in SKIP or name in skipped:
                    continue
                values = {**self.kwargs, **self.overrides.get(name, {})}
                path = reverse(name, kwargs={p: values[p] for p in params})
                with transaction.atomic():
                    before = fingerprint()
                    with transaction.atomic():
                        response = self.client.post(path, payload)
                    if response.status_code >= 500:
                        problems.append(f"{role:14} {name}: {response.status_code}")
                    elif before != fingerprint():
                        problems.append(f"{role:14} {name}: MUTATED ({response.status_code})")
                    transaction.set_rollback(True)
        self.assertFalse(problems, "\n" + "\n".join(problems))

    def test_every_url_every_role(self):
        failures, _ = self.crawl()
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


class InProgressProjectSmokeTest(SmokeTest):
    """Same crawl as the owner of an IN-PROGRESS team project, so status checks don't mask a
    GET that mutates. (Business rules can still mask some — e.g. team minimum size — which is
    why each mutating endpoint also has a targeted test in test_regressions.)"""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        amine = StudentProfile.objects.get(user__username="etu.amine")
        project = Project.objects.get(student=amine, project_assignment__module__code="WEB401")
        milestone = project.milestones.filter(completed=False).first()
        cls.kwargs.update(
            project_id=project.id,
            milestone_id=milestone.id,
            deliverable_id=project.deliverables.first().id,
            collaborator_id=project.collaborators.first().id,
            invitation_id=CollaborationInvitation.objects.get(project=project, status="pending").id,
        )
        Notification.objects.create(
            recipient=amine, notification_type="project_update", message="x"
        )
        cls.kwargs["notification_id"] = Notification.objects.filter(recipient=amine).last().id

    def test_every_url_every_role(self):
        global ROLES
        saved = ROLES
        ROLES = {"owner": "etu.amine"}
        try:
            super().test_every_url_every_role()
        finally:
            ROLES = saved
