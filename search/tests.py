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
        teacher_user = User.objects.create_user(username='prof', password='pass')
        self.teacher = TeacherProfile.objects.create(user=teacher_user, teacher_id='T001', department='Info')
        self.module = Module.objects.create(name='Django avancé', code='WEB301')
        ModuleAssignment.objects.create(teacher=self.teacher, module=self.module, is_active=True)

        # Student enrolled in the module
        student_user = User.objects.create_user(
            username='etudiant', password='pass', first_name='Amina', last_name='Benali'
        )
        self.student = StudentProfile.objects.create(
            user=student_user, student_id='E001', year_of_study=3, department='Info'
        )
        ModuleEnrollment.objects.create(student=self.student, module=self.module, is_active=True)

        # Another student with a private project (must never leak)
        other_user = User.objects.create_user(username='autre', password='pass')
        self.other_student = StudentProfile.objects.create(
            user=other_user, student_id='E002', year_of_study=3, department='Info'
        )
        self.private_project = Project.objects.create(
            title='Django secret des autres', description='d', project_type='module',
            student=self.other_student, start_date=date(2026, 1, 1),
        )

        # Student's own project (in the teacher's module)
        self.own_project = Project.objects.create(
            title='Mon app Django', description='d', project_type='module',
            student=self.student, module=self.module, start_date=date(2026, 1, 1),
        )

        # A public showcase project
        self.public_project = Project.objects.create(
            title='Django vitrine publique', description='d', project_type='module',
            student=self.other_student, start_date=date(2026, 1, 1),
            status='validated', is_public=True,
        )

        # Admin
        admin_user = User.objects.create_user(username='admin', password='pass')
        AdminProfile.objects.create(user=admin_user)

        self.url = reverse('search:search')

    def search(self, q='Django'):
        return self.client.get(self.url, {'q': q})

    def test_anonymous_sees_only_public_projects(self):
        response = self.search()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Django vitrine publique')
        self.assertNotContains(response, 'Django secret des autres')
        self.assertNotContains(response, 'Mon app Django')

    def test_student_sees_own_projects_and_modules_not_others(self):
        self.client.login(username='etudiant', password='pass')
        response = self.search()
        self.assertContains(response, 'Mon app Django')
        self.assertContains(response, 'Django vitrine publique')
        self.assertContains(response, 'WEB301')  # enrolled module
        self.assertNotContains(response, 'Django secret des autres')

    def test_teacher_sees_module_projects_and_students(self):
        self.client.login(username='prof', password='pass')
        response = self.search()
        self.assertContains(response, 'Mon app Django')  # project in their module
        self.assertNotContains(response, 'Django secret des autres')  # not in module

        response = self.search('Amina')
        self.assertContains(response, 'Amina Benali')  # enrolled student

    def test_teacher_does_not_see_students_outside_their_modules(self):
        outsider_user = User.objects.create_user(
            username='dehors', password='pass', first_name='Karim', last_name='Extérieur'
        )
        StudentProfile.objects.create(
            user=outsider_user, student_id='E003', year_of_study=4, department='Génie Civil'
        )
        self.client.login(username='prof', password='pass')
        response = self.search('Karim')
        self.assertNotContains(response, 'Karim Extérieur')

    def test_admin_sees_everything(self):
        self.client.login(username='admin', password='pass')
        response = self.search()
        self.assertContains(response, 'Mon app Django')
        self.assertContains(response, 'Django secret des autres')
        self.assertContains(response, 'Django vitrine publique')
        self.assertContains(response, 'WEB301')

        response = self.search('Amina')
        self.assertContains(response, 'Amina Benali')

    def test_empty_query_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Recherche')

    def test_filter_endpoint_redirects_to_showcase(self):
        response = self.client.get(reverse('search:filter_projects'), {'type': 'module'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/projects/', response.url)
