"""Query budgets (PLAN P3.3).

Two checks per page:
1. an absolute ceiling on the seeded demo data;
2. N+1 detection: add a batch of extra rows the page lists, and the query count
   must not grow (constant-per-page, not per-row).
"""

import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from student.models import Project, StudentProfile
from teacher.models import Module, ModuleAssignment, ModuleEnrollment, TeacherProfile


class QueryBudgetTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="budget-media-")
        cls._override = override_settings(MEDIA_ROOT=cls._media, PRIVATE_MEDIA_ROOT=cls._media)
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

    def count(self, username, url):
        self.client.force_login(User.objects.get(username=username))
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx.captured_queries)

    def grow(self, n=6):
        """Add students (with projects, enrollments) and modules (with teachers)."""
        web = Module.objects.get(code="WEB401")
        alami = TeacherProfile.objects.get(user__username="prof.alami")
        for i in range(n):
            user = User.objects.create_user(f"extra{i}", f"extra{i}@example.com", "x")
            student = StudentProfile.objects.create(
                user=user, student_id=f"X{i:03d}", year_of_study=4, department="GI"
            )
            ModuleEnrollment.objects.create(student=student, module=web)
            project = Project.objects.create(
                title=f"Extra {i}",
                description="d",
                project_type="module",
                student=student,
                start_date=timezone.localdate() - timedelta(days=3),
                module=web,
                status="submitted",
            )
            project.collaborators.add(StudentProfile.objects.exclude(pk=student.pk).first())
            module = Module.objects.create(name=f"Extra {i}", code=f"EXT{i}")
            ModuleAssignment.objects.create(teacher=alami, module=module)

    PAGES = [
        # (user, url, ceiling on seed data)
        ("admin", "/administrator/dashboard/", 30),
        ("admin", "/administrator/users/list/?type=students", 25),
        ("admin", "/administrator/users/list/?type=teachers", 25),
        ("admin", "/administrator/projects/", 30),
        ("admin", "/administrator/modules/", 20),
        ("prof.alami", "/teacher/projects/", 30),
        ("prof.alami", "/teacher/dashboard/", 30),
        ("etu.youssef", "/student/dashboard/", 30),
        ("etu.youssef", "/student/assignments/", 40),
        ("etu.youssef", "/search/?q=extra", 20),
        ("prof.alami", "/teacher/assignments/", 30),
        ("admin", "/projects/", 20),
    ]

    def test_ceilings_on_seed_data(self):
        for username, url, ceiling in self.PAGES:
            with self.subTest(url=url):
                self.assertLessEqual(self.count(username, url), ceiling)

    def test_no_n_plus_one(self):
        before = {url: self.count(u, url) for u, url, _ in self.PAGES}
        self.grow()
        for username, url, _ in self.PAGES:
            with self.subTest(url=url):
                self.assertEqual(self.count(username, url), before[url])
