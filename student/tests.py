from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Project, ProjectMilestone, StudentProfile
from teacher.models import Module, ModuleEnrollment, ProjectAssignment, TeacherProfile


class CalendarTests(TestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(username='prof', password='pass')
        self.teacher = TeacherProfile.objects.create(user=teacher_user, teacher_id='T001')
        self.module = Module.objects.create(name='Programmation Web', code='WEB301')

        student_user = User.objects.create_user(username='etudiant', password='pass')
        self.student = StudentProfile.objects.create(
            user=student_user, student_id='E001', year_of_study=3, department='Info'
        )
        ModuleEnrollment.objects.create(student=self.student, module=self.module, is_active=True)

        # Assignment deadline in 5 days
        self.deadline = timezone.now() + timedelta(days=5)
        self.assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir calendrier', description='d',
            deadline=self.deadline,
            assignment_type='direct', status='published',
        )

        # Own project with a milestone in 10 days
        self.project = Project.objects.create(
            title='Projet calendrier', description='d', project_type='module',
            student=self.student, module=self.module,
            start_date=date(2026, 1, 1),
            end_date=timezone.localtime(timezone.now()).date() + timedelta(days=20),
        )
        self.milestone = ProjectMilestone.objects.create(
            project=self.project, title='Maquette terminée',
            due_date=timezone.localtime(timezone.now()).date() + timedelta(days=10),
        )

        # Another student's milestone (must never appear)
        other_user = User.objects.create_user(username='autre', password='pass')
        other = StudentProfile.objects.create(
            user=other_user, student_id='E002', year_of_study=3, department='Info'
        )
        other_project = Project.objects.create(
            title='Projet des autres', description='d', project_type='module',
            student=other, start_date=date(2026, 1, 1),
        )
        ProjectMilestone.objects.create(
            project=other_project, title='Jalon secret',
            due_date=timezone.localtime(timezone.now()).date() + timedelta(days=3),
        )

        self.client.login(username='etudiant', password='pass')

    def test_calendar_renders_with_own_events(self):
        response = self.client.get(reverse('student:calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Devoir calendrier')
        self.assertContains(response, 'Maquette terminée')
        self.assertContains(response, 'Projet calendrier')  # end date event
        self.assertNotContains(response, 'Jalon secret')

    def test_calendar_month_navigation(self):
        response = self.client.get(reverse('student:calendar'), {'year': 2027, 'month': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Février 2027')

    def test_calendar_invalid_params_fall_back_to_today(self):
        response = self.client.get(reverse('student:calendar'), {'year': 'abc', 'month': '99'})
        self.assertEqual(response.status_code, 200)

    def test_completed_milestones_are_hidden(self):
        self.milestone.completed = True
        self.milestone.save()
        response = self.client.get(reverse('student:calendar'))
        self.assertNotContains(response, 'Maquette terminée')

    def test_ics_feed(self):
        response = self.client.get(reverse('student:calendar_ics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/calendar', response['Content-Type'])

        content = response.content.decode('utf-8')
        self.assertIn('BEGIN:VCALENDAR', content)
        self.assertIn('END:VCALENDAR', content)
        self.assertIn('Devoir calendrier', content)
        self.assertIn('Maquette terminée', content)
        self.assertNotIn('Jalon secret', content)
        # Timed deadline event uses UTC datetime, milestone is all-day
        self.assertIn(f"UID:assignment-{self.assignment.id}-deadline@ensa-project-manager", content)
        self.assertIn('DTSTART;VALUE=DATE:', content)

    def test_calendar_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('student:calendar'))
        self.assertEqual(response.status_code, 302)
