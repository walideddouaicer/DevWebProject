import shutil
import tempfile
from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Module, ModuleAssignment, TeacherProfile
from student.models import (
    DeliverableComment,
    Notification,
    Project,
    ProjectComment,
    ProjectDeliverable,
    StudentProfile,
)

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class DeliverableFeedbackTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        teacher_user = User.objects.create_user(username='prof', password='profpass')
        self.teacher = TeacherProfile.objects.create(user=teacher_user, teacher_id='T001')

        student_user = User.objects.create_user(username='etudiant', password='etupass')
        self.student = StudentProfile.objects.create(
            user=student_user, student_id='E001', year_of_study=3, department='Informatique'
        )

        self.module = Module.objects.create(name='Programmation Web', code='WEB301')
        ModuleAssignment.objects.create(teacher=self.teacher, module=self.module, is_active=True)

        self.project = Project.objects.create(
            title='Projet Test',
            description='Description',
            project_type='module',
            student=self.student,
            module=self.module,
            start_date=date(2026, 1, 1),
            status='submitted',
        )

        self.deliverable = ProjectDeliverable.objects.create(
            project=self.project,
            file=SimpleUploadedFile('rapport.pdf', b'contenu'),
            file_type='report',
            name='Rapport final',
        )

    def login_teacher(self):
        self.client.login(username='prof', password='profpass')

    def login_student(self):
        self.client.login(username='etudiant', password='etupass')

    def test_teacher_requests_revision(self):
        self.login_teacher()
        response = self.client.post(
            reverse('teacher:request_revision', args=[self.project.id]),
            {'content': 'Veuillez compléter la section 3 du rapport.'},
        )
        self.assertEqual(response.status_code, 302)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'revision_requested')
        self.assertTrue(
            ProjectComment.objects.filter(
                project=self.project, content__contains='Veuillez compléter la section 3'
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.student, project=self.project).exists()
        )

    def test_request_revision_requires_content(self):
        self.login_teacher()
        self.client.post(reverse('teacher:request_revision', args=[self.project.id]), {'content': '  '})

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'submitted')

    def test_teacher_comments_on_deliverable(self):
        self.login_teacher()
        response = self.client.post(
            reverse('teacher:add_deliverable_comment', args=[self.deliverable.id]),
            {'content': 'Le rapport manque de sources.'},
        )
        self.assertEqual(response.status_code, 302)

        comment = DeliverableComment.objects.get(deliverable=self.deliverable)
        self.assertEqual(comment.author, self.teacher.user)
        self.assertTrue(comment.is_teacher_comment)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student, notification_type='deliverable'
            ).exists()
        )

    def test_student_replies_on_deliverable(self):
        self.login_student()
        self.client.post(
            reverse('student:add_deliverable_comment', args=[self.deliverable.id]),
            {'content': 'Sources ajoutées dans la nouvelle version.'},
        )

        comment = DeliverableComment.objects.get(deliverable=self.deliverable)
        self.assertEqual(comment.author, self.student.user)
        self.assertFalse(comment.is_teacher_comment)

    def test_other_student_cannot_comment_on_deliverable(self):
        outsider = User.objects.create_user(username='intrus', password='intruspass')
        StudentProfile.objects.create(
            user=outsider, student_id='E002', year_of_study=3, department='Informatique'
        )
        self.client.login(username='intrus', password='intruspass')

        self.client.post(
            reverse('student:add_deliverable_comment', args=[self.deliverable.id]),
            {'content': 'Je ne devrais pas pouvoir commenter.'},
        )
        self.assertEqual(DeliverableComment.objects.count(), 0)

    def test_student_can_resubmit_after_revision_request(self):
        self.project.status = 'revision_requested'
        self.project.save()

        self.login_student()
        response = self.client.post(reverse('student:project_submit', args=[self.project.id]))
        self.assertEqual(response.status_code, 302)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'submitted')
