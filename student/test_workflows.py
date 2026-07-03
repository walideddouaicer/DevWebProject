# Core-workflow tests (ROADMAP #15): team-size rules, option claiming,
# registration approval atomicity, and the assignment submission workflow.
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Project, StudentProfile
from teacher.models import (
    Module, ModuleAssignment, ModuleEnrollment,
    ProjectAssignment, ProjectOption, TeacherProfile,
)


def make_student(username, sid, module=None):
    user = User.objects.create_user(
        username=username, password='pass',
        first_name=username.capitalize(), last_name='Test',
    )
    profile = StudentProfile.objects.create(
        user=user, student_id=sid, year_of_study=3, department='Info'
    )
    if module:
        ModuleEnrollment.objects.create(student=profile, module=module, is_active=True)
    return profile


class TeamSizeRulesTests(TestCase):
    """Project team-size validation against assignment constraints."""

    def setUp(self):
        teacher_user = User.objects.create_user(username='prof', password='pass')
        self.teacher = TeacherProfile.objects.create(user=teacher_user, teacher_id='T001')
        self.module = Module.objects.create(name='Web', code='WEB301')

        self.assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir équipe', description='d',
            deadline=timezone.now() + timedelta(days=14),
            selection_deadline=timezone.now() + timedelta(days=7),
            assignment_type='choice_based', status='published',
            is_team_work=True, min_team_size=2, max_team_size=3,
        )

        self.owner = make_student('owner', 'E001', self.module)
        self.mate1 = make_student('mate1', 'E002', self.module)
        self.mate2 = make_student('mate2', 'E003', self.module)
        self.mate3 = make_student('mate3', 'E004', self.module)

        self.project = Project.objects.create(
            title='Team project', description='d', project_type='module',
            student=self.owner, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=self.assignment,
        )

    def test_solo_team_below_minimum_is_invalid(self):
        self.assertFalse(self.project.is_team_size_valid())
        self.assertEqual(self.project.get_team_size_status()['status'], 'too_small')

    def test_valid_range_and_full_team(self):
        self.project.collaborators.add(self.mate1)
        self.assertTrue(self.project.is_team_size_valid())
        self.assertEqual(self.project.get_team_size_status()['status'], 'optimal')

        self.project.collaborators.add(self.mate2)
        self.assertTrue(self.project.is_team_size_valid())
        status = self.project.get_team_size_status()
        self.assertEqual(status['status'], 'full')
        self.assertFalse(status['can_invite'])
        self.assertFalse(self.project.can_invite_more_collaborators())
        self.assertEqual(self.project.get_remaining_team_slots(), 0)

    def test_add_collaborator_beyond_max_is_rejected(self):
        self.project.collaborators.add(self.mate1, self.mate2)  # full (3/3)
        with self.assertRaises(ValidationError):
            self.project.add_assignment_collaborator(self.mate3)
        self.assertEqual(self.project.get_team_size(), 3)

    def test_add_collaborator_not_enrolled_is_rejected(self):
        stranger = make_student('stranger', 'E999')  # not enrolled
        with self.assertRaises(ValidationError):
            self.project.add_assignment_collaborator(stranger)

    def test_add_collaborator_already_on_assignment_is_rejected(self):
        Project.objects.create(
            title='Autre équipe', description='d', project_type='module',
            student=self.mate1, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=self.assignment,
        )
        with self.assertRaises(ValidationError):
            self.project.add_assignment_collaborator(self.mate1)

    def test_remove_collaborator_below_minimum_is_rejected(self):
        self.project.collaborators.add(self.mate1)  # exactly min (2)
        with self.assertRaises(ValidationError):
            self.project.remove_assignment_collaborator(self.mate1)

    def test_owner_cannot_be_removed(self):
        with self.assertRaises(ValidationError):
            self.project.remove_assignment_collaborator(self.owner)

    def test_individual_assignment_forbids_collaborators(self):
        solo_assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir individuel', description='d',
            deadline=timezone.now() + timedelta(days=14),
            assignment_type='direct', status='published',
            is_team_work=False,
        )
        solo_project = Project.objects.create(
            title='Solo', description='d', project_type='module',
            student=self.owner, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=solo_assignment,
        )
        self.assertFalse(solo_project.can_invite_more_collaborators())
        with self.assertRaises(ValidationError):
            solo_project.add_assignment_collaborator(self.mate1)


class OptionClaimingTests(TestCase):
    """Unique project options can only be claimed once."""

    def setUp(self):
        teacher_user = User.objects.create_user(username='prof', password='pass')
        self.teacher = TeacherProfile.objects.create(user=teacher_user, teacher_id='T001')
        self.module = Module.objects.create(name='Web', code='WEB301')

        self.assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir choix', description='d',
            deadline=timezone.now() + timedelta(days=14),
            selection_deadline=timezone.now() + timedelta(days=7),
            assignment_type='choice_based', status='published',
        )
        self.option = ProjectOption.objects.create(
            assignment=self.assignment,
            title='Sujet unique', description='Un sujet très convoité pour ce devoir',
            is_unique=True, max_teams=1,
        )

        self.alice = make_student('alice', 'E001', self.module)
        self.bob = make_student('bob', 'E002', self.module)

    def create_project_via_endpoint(self, username):
        self.client.login(username=username, password='pass')
        url = reverse('student:create_assignment_project_direct', args=[self.assignment.id])
        return self.client.post(f"{url}?option_id={self.option.id}", {
            'title': self.option.title,
            'description': self.option.description,
            'project_type': 'module',
            'start_date': '2026-01-01',
            'selected_option_id': self.option.id,
        })

    def test_unique_option_cannot_be_claimed_twice(self):
        response = self.client.get('/')  # warm up
        response = self.create_project_via_endpoint('alice')
        self.assertEqual(response.status_code, 302)

        self.option.refresh_from_db()
        self.assertEqual(self.option.current_teams, 1)
        self.assertFalse(self.option.is_selectable())

        # Bob tries the same option: no project created, counter unchanged
        self.create_project_via_endpoint('bob')
        self.option.refresh_from_db()
        self.assertEqual(self.option.current_teams, 1)
        self.assertEqual(Project.objects.filter(
            project_assignment=self.assignment, student=self.bob
        ).count(), 0)

    def test_release_frees_the_option(self):
        self.create_project_via_endpoint('alice')
        project = Project.objects.get(project_assignment=self.assignment, student=self.alice)

        self.option.refresh_from_db()
        self.option.release_from_team(project)

        self.option.refresh_from_db()
        self.assertEqual(self.option.current_teams, 0)
        self.assertTrue(self.option.is_selectable())


class RegistrationApprovalAtomicityTests(TestCase):
    """Approving a registration must be all-or-nothing."""

    def setUp(self):
        from administrator.models import AdminProfile
        admin_user = User.objects.create_user(username='admin', password='adminpass')
        AdminProfile.objects.create(user=admin_user, admin_id='A001')
        self.client.login(username='admin', password='adminpass')

    def test_duplicate_student_id_leaves_no_orphan_user(self):
        from django.contrib.auth.hashers import make_password
        from accounts.models import PendingRegistration

        # The student_id is already taken
        existing = make_student('taken', 'E777')

        registration = PendingRegistration.objects.create(
            email='new@x.com', first_name='N', last_name='S', username='newstud',
            password=make_password('pass12345'), role='student',
            student_id='E777',  # duplicate!
            year_of_study=3, department='Info',
        )

        self.client.post(reverse('administrator:approve_registration', args=[registration.id]))

        # No half-created account: the User must NOT exist
        self.assertFalse(User.objects.filter(username='newstud').exists())
        registration.refresh_from_db()
        self.assertFalse(registration.is_approved)

        # And a second attempt after fixing the conflict succeeds
        registration.student_id = 'E778'
        registration.save()
        self.client.post(reverse('administrator:approve_registration', args=[registration.id]))
        self.assertTrue(User.objects.filter(username='newstud').exists())
        self.assertTrue(StudentProfile.objects.filter(student_id='E778').exists())


class SubmissionWorkflowTests(TestCase):
    """Assignment submission eligibility rules."""

    def setUp(self):
        teacher_user = User.objects.create_user(username='prof', password='pass')
        self.teacher = TeacherProfile.objects.create(user=teacher_user, teacher_id='T001')
        self.module = Module.objects.create(name='Web', code='WEB301')
        self.student = make_student('etudiant', 'E001', self.module)

        self.assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir soumission', description='d',
            deadline=timezone.now() + timedelta(days=14),
            assignment_type='direct', status='published',
        )
        self.project = Project.objects.create(
            title='À soumettre', description='d', project_type='module',
            student=self.student, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=self.assignment,
        )

    def test_submittable_when_valid(self):
        self.assertTrue(self.project.can_be_submitted_for_assignment())

    def test_not_submittable_after_deadline(self):
        ProjectAssignment.objects.filter(id=self.assignment.id).update(
            deadline=timezone.now() - timedelta(hours=1)
        )
        self.project.refresh_from_db()
        self.assertFalse(self.project.can_be_submitted_for_assignment())

    def test_not_submittable_twice(self):
        self.project.status = 'submitted'
        self.project.save()
        self.assertFalse(self.project.can_be_submitted_for_assignment())

    def test_choice_based_requires_selected_option(self):
        choice_assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir choix', description='d',
            deadline=timezone.now() + timedelta(days=14),
            selection_deadline=timezone.now() + timedelta(days=7),
            assignment_type='choice_based', status='published',
        )
        project = Project.objects.create(
            title='Sans option', description='d', project_type='module',
            student=self.student, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=choice_assignment,
        )
        self.assertFalse(project.can_be_submitted_for_assignment())

    def test_submit_endpoint_blocks_undersized_team(self):
        team_assignment = ProjectAssignment.objects.create(
            teacher=self.teacher, module=self.module,
            title='Devoir équipe min', description='d',
            deadline=timezone.now() + timedelta(days=14),
            assignment_type='direct', status='published',
            is_team_work=True, min_team_size=2, max_team_size=4,
        )
        project = Project.objects.create(
            title='Solo sur devoir équipe', description='d', project_type='module',
            student=self.student, module=self.module,
            start_date=date(2026, 1, 1), status='in_progress',
            assignment_source='teacher_assigned', project_assignment=team_assignment,
        )

        self.client.login(username='etudiant', password='pass')
        self.client.post(reverse('student:project_submit', args=[project.id]))

        project.refresh_from_db()
        self.assertEqual(project.status, 'in_progress')  # blocked
