from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.permissions import (
    admin_required,
    get_project_for_member,
    get_project_for_owner,
    get_project_for_teacher,
    get_role,
    student_required,
    teacher_required,
)
from administrator.models import AdminProfile
from student.models import Project, StudentProfile
from teacher.models import Module, ModuleAssignment, TeacherProfile


def ok_view(request):
    return HttpResponse("ok")


class PermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def user(name):
            return User.objects.create_user(name, f"{name}@example.com", "x")

        cls.students = [
            StudentProfile.objects.create(
                user=user(f"s{i}"), student_id=f"S{i}", year_of_study=4, department="GI"
            )
            for i in range(4)
        ]
        cls.teacher = TeacherProfile.objects.create(user=user("t"), teacher_id="T1")
        cls.other_teacher = TeacherProfile.objects.create(user=user("t2"), teacher_id="T2")
        cls.admin = AdminProfile.objects.create(user=user("a"), admin_id="A1")
        cls.module = Module.objects.create(name="Web", code="WEB1")
        ModuleAssignment.objects.create(teacher=cls.teacher, module=cls.module)
        cls.project = Project.objects.create(
            title="P",
            description="d",
            project_type="module",
            student=cls.students[0],
            start_date=timezone.localdate(),
            module=cls.module,
        )
        cls.project.collaborators.add(cls.students[1], cls.students[2])

    def request(self, user):
        request = RequestFactory().get("/somewhere/?x=1")
        request.user = user
        return request

    def test_roles(self):
        self.assertEqual(get_role(self.students[0].user), "student")
        self.assertEqual(get_role(self.teacher.user), "teacher")
        self.assertEqual(get_role(self.admin.user), "admin")
        self.assertIsNone(get_role(AnonymousUser()))

    def test_anonymous_is_redirected_to_login_with_next(self):
        for decorator in (student_required, teacher_required, admin_required):
            response = decorator(ok_view)(self.request(AnonymousUser()))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/?next=/somewhere/%3Fx%3D1", response["Location"])

    def test_wrong_role_is_forbidden(self):
        cases = [
            (student_required, self.teacher.user),
            (teacher_required, self.students[0].user),
            (admin_required, self.teacher.user),
        ]
        for decorator, user in cases:
            with self.assertRaises(PermissionDenied):
                decorator(ok_view)(self.request(user))

    def test_right_role_passes_and_profile_is_attached(self):
        request = self.request(self.students[0].user)
        self.assertEqual(student_required(ok_view)(request).status_code, 200)
        self.assertEqual(request.student, self.students[0])
        request = self.request(self.teacher.user)
        teacher_required(ok_view)(request)
        self.assertEqual(request.teacher, self.teacher)
        request = self.request(self.admin.user)
        admin_required(ok_view)(request)
        self.assertEqual(request.admin_profile, self.admin)

    def test_member_access_with_many_collaborators(self):
        for student in self.students[:3]:
            self.assertEqual(get_project_for_member(student, self.project.id), self.project)
        with self.assertRaises(Http404):
            get_project_for_member(self.students[3], self.project.id)

    def test_owner_access(self):
        self.assertEqual(get_project_for_owner(self.students[0], self.project.id), self.project)
        with self.assertRaises(Http404):
            get_project_for_owner(self.students[1], self.project.id)

    def test_teacher_access_is_module_scoped(self):
        self.assertEqual(get_project_for_teacher(self.teacher, self.project.id), self.project)
        with self.assertRaises(Http404):
            get_project_for_teacher(self.other_teacher, self.project.id)
