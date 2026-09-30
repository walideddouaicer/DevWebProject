"""Form-backed POST handling (PLAN P3.2)."""

from django.urls import reverse

from student.models import ProjectComment
from teacher.models import Module, ProjectEvaluation

from .test_regressions import Fixtures


class AdminModuleFormTests(Fixtures):
    def test_create_validates_and_uppercases_code(self):
        self.login(self.admin)
        data = {
            "name": "Réseaux",
            "code": "res201",
            "academic_year": "2026-2027",
            "semester": "S1",
            "is_active": "on",
        }
        self.client.post(reverse("administrator:module_create"), data)
        self.assertTrue(Module.objects.filter(code="RES201").exists())
        # duplicate code and bad year are rejected
        self.client.post(reverse("administrator:module_create"), {**data, "name": "Autre"})
        self.assertEqual(Module.objects.filter(code="RES201").count(), 1)
        self.client.post(
            reverse("administrator:module_create"), {**data, "code": "NEW1", "academic_year": "26"}
        )
        self.assertFalse(Module.objects.filter(code="NEW1").exists())

    def test_edit_keeps_code_and_unshown_fields(self):
        self.module.classroom = "Salle B12"
        self.module.save()
        self.login(self.admin)
        self.client.post(
            reverse("administrator:module_edit", args=[self.module.id]),
            {
                "name": "Web avancé",
                "code": "HACKED",
                "academic_year": "2026-2027",
                "semester": "S2",
                "is_active": "on",
            },
        )
        self.module.refresh_from_db()
        self.assertEqual(self.module.name, "Web avancé")
        self.assertEqual(self.module.code, "WEB1")
        self.assertEqual(self.module.classroom, "Salle B12")


class TeacherFormTests(Fixtures):
    def test_comment_length_is_limited(self):
        project = self.project(self.students[0])
        self.login(self.teacher)
        self.client.post(
            reverse("teacher:add_teacher_comment", args=[project.id]), {"content": "x" * 6000}
        )
        self.assertFalse(ProjectComment.objects.exists())
        self.client.post(
            reverse("teacher:add_teacher_comment", args=[project.id]), {"content": "Bien"}
        )
        self.assertEqual(ProjectComment.objects.count(), 1)

    def test_grade_accepts_french_decimal_and_rubric(self):
        project = self.project(self.students[0], status="submitted")
        self.login(self.teacher)
        self.client.post(
            reverse("teacher:grade_project", args=[project.id]),
            {
                "score": "15,5",
                "comments": "Solide",
                "criterion_name": ["Code", ""],
                "criterion_score": ["16,25", ""],
                "criterion_comment": ["", ""],
            },
        )
        evaluation = ProjectEvaluation.objects.get(project=project)
        self.assertEqual(str(evaluation.score), "15.50")
        self.assertEqual(evaluation.criteria.get().name, "Code")

    def test_grade_rejects_out_of_range(self):
        project = self.project(self.students[0], status="submitted")
        self.login(self.teacher)
        self.client.post(reverse("teacher:grade_project", args=[project.id]), {"score": "21"})
        self.assertFalse(ProjectEvaluation.objects.exists())

    def test_bulk_revision_requires_message(self):
        assignment = self.assignment()
        project = self.project(self.students[0], assignment=assignment, status="submitted")
        self.login(self.teacher)
        url = reverse("teacher:bulk_project_action", args=[assignment.id])
        self.client.post(url, {"action": "revision", "project_ids": [project.id]})
        project.refresh_from_db()
        self.assertEqual(project.status, "submitted")
        self.client.post(url, {"action": "bogus", "project_ids": [project.id]})
        project.refresh_from_db()
        self.assertEqual(project.status, "submitted")
        self.client.post(url, {"action": "validate", "project_ids": [project.id, 99999]})
        project.refresh_from_db()
        self.assertEqual(project.status, "validated")
