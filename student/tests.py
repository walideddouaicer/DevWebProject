import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Project, ProjectDeliverable, ProjectMilestone, StudentProfile, TeammateRequest
from teacher.models import Module, ModuleEnrollment, ProjectAssignment, TeacherProfile

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


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


class DailyDigestTests(TestCase):
    def setUp(self):
        from .models import Notification, UserPreferences

        def make_student(name, sid, digest):
            user = User.objects.create_user(username=name, password='pass', email=f'{name}@x.com')
            profile = StudentProfile.objects.create(
                user=user, student_id=sid, year_of_study=3, department='Info'
            )
            UserPreferences.objects.create(user=user, email_digest=digest)
            return profile

        self.digest_student = make_student('digestuser', 'E001', True)
        self.instant_student = make_student('instantuser', 'E002', False)

        # Unread notifications for both
        for student in (self.digest_student, self.instant_student):
            Notification.objects.create(
                recipient=student, notification_type='project_update',
                message='Quelque chose est arrivé'
            )
            Notification.objects.create(
                recipient=student, notification_type='project_update',
                message='Autre événement'
            )

    def run_digest(self, **kwargs):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('send_daily_digest', stdout=out, **kwargs)
        return out.getvalue()

    def test_digest_sent_only_to_digest_users(self):
        from django.core import mail
        self.run_digest()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['digestuser@x.com'])
        self.assertIn('2 notification(s)', message.subject)
        self.assertIn('Quelque chose est arrivé', message.body)

    def test_no_digest_when_nothing_unread(self):
        from django.core import mail
        from .models import Notification
        Notification.objects.filter(recipient=self.digest_student).update(is_read=True)

        self.run_digest()
        self.assertEqual(len(mail.outbox), 0)

    def test_digest_respects_email_notifications_off(self):
        from django.core import mail
        prefs = self.digest_student.user.preferences
        prefs.email_notifications = False
        prefs.save()

        self.run_digest()
        self.assertEqual(len(mail.outbox), 0)

    def test_invitation_email_skipped_for_digest_users(self):
        from django.core import mail
        from .models import CollaborationInvitation, Project
        from .utils import send_invitation_email

        project = Project.objects.create(
            title='P', description='d', project_type='module',
            student=self.instant_student, start_date=date(2026, 1, 1),
        )
        invitation = CollaborationInvitation.objects.create(
            project=project, sender=self.instant_student,
            recipient=self.digest_student, status='pending',
        )
        result = send_invitation_email(invitation)
        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

        # Instant user still gets the email
        invitation2 = CollaborationInvitation.objects.create(
            project=project, sender=self.digest_student,
            recipient=self.instant_student, status='pending',
        )
        # give digest_student a project to invite from is irrelevant here;
        # we only check the email path
        self.assertTrue(send_invitation_email(invitation2))
        self.assertEqual(len(mail.outbox), 1)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class DeliverableVersioningTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        user = User.objects.create_user(username='etudiant', password='pass')
        self.student = StudentProfile.objects.create(
            user=user, student_id='E001', year_of_study=3, department='Info'
        )
        self.project = Project.objects.create(
            title='Projet versions', description='d', project_type='module',
            student=self.student, start_date=date(2026, 1, 1), status='in_progress',
        )
        self.client.login(username='etudiant', password='pass')
        self.upload_url = reverse('student:upload_deliverable', args=[self.project.id])

    def upload(self, name):
        return self.client.post(self.upload_url, {
            'file': SimpleUploadedFile('rapport.pdf', b'contenu'),
            'file_type': 'report',
            'name': name,
        })

    def test_same_name_increments_version(self):
        self.upload('Rapport final')
        self.upload('Rapport final')
        self.upload('Autre document')

        versions = list(ProjectDeliverable.objects.filter(
            project=self.project, name='Rapport final'
        ).order_by('version').values_list('version', flat=True))
        self.assertEqual(versions, [1, 2])

        other = ProjectDeliverable.objects.get(project=self.project, name='Autre document')
        self.assertEqual(other.version, 1)

    def test_group_deliverables_returns_latest_with_history(self):
        from .utils import group_deliverables
        self.upload('Rapport final')
        self.upload('Rapport final')
        self.upload('Rapport final')

        grouped = group_deliverables(ProjectDeliverable.objects.filter(project=self.project))
        self.assertEqual(len(grouped), 1)
        latest = grouped[0]
        self.assertEqual(latest.version, 3)
        self.assertEqual([d.version for d in latest.history], [2, 1])

    def test_project_page_shows_version_badge_and_history(self):
        self.upload('Rapport final')
        self.upload('Rapport final')

        response = self.client.get(reverse('student:project_detail', args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'v2')
        self.assertContains(response, 'ancienne')
        # Only one card for the deliverable (grouped), counted once
        self.assertContains(response, '1 livrable')


class TeammatesBoardTests(TestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(username='prof', password='pass')
        self.teacher = TeacherProfile.objects.create(user=teacher_user, teacher_id='T001')
        self.module = Module.objects.create(name='Programmation Web', code='WEB301')

        def make_student(name, sid):
            user = User.objects.create_user(
                username=name, password='pass', first_name=name.capitalize(), last_name='Test'
            )
            profile = StudentProfile.objects.create(
                user=user, student_id=sid, year_of_study=3, department='Info'
            )
            ModuleEnrollment.objects.create(student=profile, module=self.module, is_active=True)
            return profile

        self.student = make_student('alice', 'E001')
        self.seeker = make_student('bob', 'E002')
        self.outsider_user = User.objects.create_user(username='eve', password='pass')
        self.outsider = StudentProfile.objects.create(
            user=self.outsider_user, student_id='E003', year_of_study=3, department='Info'
        )  # NOT enrolled

        self.assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir équipe', description='d',
            deadline=timezone.now() + timedelta(days=14),
            selection_deadline=timezone.now() + timedelta(days=7),
            assignment_type='choice_based', status='published',
            is_team_work=True, min_team_size=2, max_team_size=4,
        )

        self.board_url = reverse('student:teammates_board', args=[self.assignment.id])
        self.toggle_url = reverse('student:toggle_teammate_request', args=[self.assignment.id])

    def test_flag_and_appear_on_board(self):
        self.client.login(username='bob', password='pass')
        response = self.client.post(self.toggle_url, {'action': 'flag', 'message': 'Je connais Django'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TeammateRequest.objects.filter(
            assignment=self.assignment, student=self.seeker, is_active=True
        ).exists())

        # Alice sees Bob on the board
        self.client.login(username='alice', password='pass')
        response = self.client.get(self.board_url)
        self.assertContains(response, 'Bob Test')
        self.assertContains(response, 'Je connais Django')

    def test_unflag_removes_from_board(self):
        TeammateRequest.objects.create(assignment=self.assignment, student=self.seeker)
        self.client.login(username='bob', password='pass')
        self.client.post(self.toggle_url, {'action': 'unflag'})
        self.assertFalse(TeammateRequest.objects.get(
            assignment=self.assignment, student=self.seeker
        ).is_active)

    def test_students_with_a_team_are_hidden(self):
        TeammateRequest.objects.create(assignment=self.assignment, student=self.seeker)
        # Bob then creates a project for the assignment
        Project.objects.create(
            title='Projet de Bob', description='d', project_type='module',
            student=self.seeker, module=self.module,
            start_date=date(2026, 1, 1),
            assignment_source='teacher_assigned', project_assignment=self.assignment,
        )
        self.client.login(username='alice', password='pass')
        response = self.client.get(self.board_url)
        self.assertNotContains(response, 'Bob Test')

    def test_cannot_flag_when_already_in_team(self):
        Project.objects.create(
            title='Projet de Bob', description='d', project_type='module',
            student=self.seeker, module=self.module,
            start_date=date(2026, 1, 1),
            assignment_source='teacher_assigned', project_assignment=self.assignment,
        )
        self.client.login(username='bob', password='pass')
        self.client.post(self.toggle_url, {'action': 'flag'})
        self.assertFalse(TeammateRequest.objects.filter(
            assignment=self.assignment, student=self.seeker, is_active=True
        ).exists())

    def test_board_requires_enrollment(self):
        self.client.login(username='eve', password='pass')
        response = self.client.get(self.board_url)
        self.assertEqual(response.status_code, 404)

    def test_project_owner_sees_invite_button(self):
        Project.objects.create(
            title='Projet Alice', description='d', project_type='module',
            student=self.student, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=self.assignment,
        )
        TeammateRequest.objects.create(assignment=self.assignment, student=self.seeker)

        self.client.login(username='alice', password='pass')
        response = self.client.get(self.board_url)
        self.assertContains(response, 'Inviter')

    def test_accepting_invitation_deactivates_flag(self):
        from .models import CollaborationInvitation
        TeammateRequest.objects.create(assignment=self.assignment, student=self.seeker)
        project = Project.objects.create(
            title='Projet Alice', description='d', project_type='module',
            student=self.student, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=self.assignment,
        )
        invitation = CollaborationInvitation.objects.create(
            project=project, sender=self.student, recipient=self.seeker, status='pending'
        )

        self.client.login(username='bob', password='pass')
        self.client.get(reverse('student:respond_to_invitation', args=[invitation.id, 'accept']))

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'accepted')
        self.assertFalse(TeammateRequest.objects.get(
            assignment=self.assignment, student=self.seeker
        ).is_active)
