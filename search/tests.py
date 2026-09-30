from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from administrator.models import AdminProfile
from student.models import Project, StudentProfile
from teacher.models import Module, ModuleAssignment, ModuleEnrollment, TeacherProfile


class GlobalSearchTests(TestCase):
    def setUp(self):
        # Teacher with a module
        teacher_user = User.objects.create_user(username="prof", password="pass")
        self.teacher = TeacherProfile.objects.create(
            user=teacher_user, teacher_id="T001", department="Info"
        )
        self.module = Module.objects.create(name="Django avancé", code="WEB301")
        ModuleAssignment.objects.create(teacher=self.teacher, module=self.module, is_active=True)

        # Student enrolled in the module
        student_user = User.objects.create_user(
            username="etudiant", password="pass", first_name="Amina", last_name="Benali"
        )
        self.student = StudentProfile.objects.create(
            user=student_user, student_id="E001", year_of_study=3, department="Info"
        )
        ModuleEnrollment.objects.create(student=self.student, module=self.module, is_active=True)

        # Another student with a private project (must never leak)
        other_user = User.objects.create_user(username="autre", password="pass")
        self.other_student = StudentProfile.objects.create(
            user=other_user, student_id="E002", year_of_study=3, department="Info"
        )
        self.private_project = Project.objects.create(
            title="Django secret des autres",
            description="d",
            project_type="module",
            student=self.other_student,
            start_date=date(2026, 1, 1),
        )

        # Student's own project (in the teacher's module)
        self.own_project = Project.objects.create(
            title="Mon app Django",
            description="d",
            project_type="module",
            student=self.student,
            module=self.module,
            start_date=date(2026, 1, 1),
        )

        # A public showcase project
        self.public_project = Project.objects.create(
            title="Django vitrine publique",
            description="d",
            project_type="module",
            student=self.other_student,
            start_date=date(2026, 1, 1),
            status="validated",
            is_public=True,
        )

        # Admin
        admin_user = User.objects.create_user(username="admin", password="pass")
        AdminProfile.objects.create(user=admin_user)

        self.url = reverse("search:search")

    def search(self, q="Django"):
        return self.client.get(self.url, {"q": q})

    def titles(self, q="Django"):
        response = self.search(q)
        self.assertEqual(response.status_code, 200)
        return {item.title for section in response.context["sections"] for item in section.items}

    def test_anonymous_sees_only_public_projects(self):
        self.assertEqual(self.titles(), {"Django vitrine publique"})

    def test_student_sees_own_projects_and_modules_not_others(self):
        self.client.login(username="etudiant", password="pass")
        self.assertEqual(
            self.titles(),
            {"Mon app Django", "Django vitrine publique", "WEB301 — Django avancé"},
        )

    def test_teacher_sees_module_projects_and_students(self):
        self.client.login(username="prof", password="pass")
        titles = self.titles()
        self.assertIn("Mon app Django", titles)  # project in their module
        self.assertNotIn("Django secret des autres", titles)  # not in module
        self.assertIn("Amina Benali", self.titles("Amina"))  # enrolled student

    def test_teacher_does_not_see_students_outside_their_modules(self):
        outsider_user = User.objects.create_user(
            username="dehors", password="pass", first_name="Karim", last_name="Extérieur"
        )
        StudentProfile.objects.create(
            user=outsider_user, student_id="E003", year_of_study=4, department="Génie Civil"
        )
        self.client.login(username="prof", password="pass")
        self.assertEqual(self.titles("Karim"), set())

    def test_admin_sees_everything(self):
        self.client.login(username="admin", password="pass")
        self.assertEqual(
            self.titles(),
            {
                "Mon app Django",
                "Django secret des autres",
                "Django vitrine publique",
                "WEB301 — Django avancé",
            },
        )
        self.assertIn("Amina Benali", self.titles("Amina"))

    def test_module_code_finds_member_projects_only(self):
        self.client.login(username="prof", password="pass")
        titles = self.titles("WEB301")
        self.assertIn("Mon app Django", titles)
        self.assertNotIn("Django secret des autres", titles)

    def test_matches_are_highlighted_and_escaped(self):
        self.private_project.title = "<b>Django</b> secret"
        self.private_project.save()
        self.client.login(username="admin", password="pass")
        response = self.search()
        self.assertContains(response, "&lt;b&gt;<mark>Django</mark>&lt;/b&gt; secret")
        self.assertNotContains(response, "<b>Django</b>")

    def test_one_character_query_searches_nothing(self):
        self.client.login(username="admin", password="pass")
        response = self.search("D")
        self.assertEqual(response.context["sections"], [])
        self.assertContains(response, "au moins deux caractères")

    def test_quick_search_partial(self):
        self.client.login(username="etudiant", password="pass")
        response = self.client.get(reverse("search:quick"), {"q": "Django"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")
        self.assertContains(response, reverse("student:project_detail", args=[self.own_project.id]))
        self.assertContains(response, "Tous les résultats")
        self.assertNotContains(response, "secret des autres")

    def test_quick_search_ignores_short_queries(self):
        response = self.client.get(reverse("search:quick"), {"q": "D"})
        self.assertEqual(response.content.strip(), b"")

    def test_teacher_people_search_has_no_n_plus_one(self):
        for i in range(5):
            user = User.objects.create_user(
                username=f"amina{i}", password="pass", first_name="Amina", last_name=f"N{i}"
            )
            profile = StudentProfile.objects.create(
                user=user, student_id=f"E1{i}", year_of_study=3, department="Info"
            )
            ModuleEnrollment.objects.create(student=profile, module=self.module, is_active=True)
        self.client.login(username="prof", password="pass")
        self.search("Amina")  # warm session/profile caches
        with self.assertNumQueries(15) as ctx:
            titles = self.titles("Amina")
        self.assertEqual(len(titles), 6, ctx)

    def test_empty_query_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recherche")

    def test_filter_endpoint_redirects_to_showcase(self):
        response = self.client.get(reverse("search:filter_projects"), {"type": "module"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/projects/", response.url)
