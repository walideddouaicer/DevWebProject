"""Project state machine (PLAN P1.3)."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from student.models import Notification, ProjectActivity, ProjectComment
from teacher.models import DirectStudentAssignment, ProjectOption

from .test_regressions import Fixtures


class WorkflowTests(Fixtures):
    def team_project(self, size=2, **assignment_fields):
        s = self.students
        fields = dict(
            is_team_work=True,
            min_team_size=2,
            max_team_size=3,
            target_selection="specific_students",
        )
        fields.update(assignment_fields)
        assignment = self.assignment(**fields)
        for student in s[:size]:
            DirectStudentAssignment.objects.create(
                assignment=assignment, student=student, status="started"
            )
        return self.project(s[0], s[1:size], assignment=assignment)

    def dsa_statuses(self, project):
        return set(
            DirectStudentAssignment.objects.filter(
                assignment=project.project_assignment
            ).values_list("status", flat=True)
        )

    # ---------------------------------------------------------------- submit
    def test_submit_syncs_team_and_notifies_others(self):
        project = self.team_project(size=3)
        project.submit(by=self.students[0])
        project.refresh_from_db()
        self.assertEqual(project.status, "submitted")
        self.assertIsNotNone(project.assignment_submitted_at)
        self.assertEqual(self.dsa_statuses(project), {"submitted"})
        notified = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(notified, {self.students[1].id, self.students[2].id})
        self.assertTrue(
            ProjectActivity.objects.filter(project=project, activity_type="assignment_submitted")
        )

    def test_only_owner_can_submit(self):
        project = self.team_project()
        with self.assertRaises(ValidationError):
            project.submit(by=self.students[1])

    def test_cannot_submit_undersized_team(self):
        project = self.team_project(size=1)
        with self.assertRaisesMessage(ValidationError, "minimum"):
            project.submit(by=self.students[0])

    def test_cannot_submit_oversized_team(self):
        project = self.team_project(size=2, min_team_size=2, max_team_size=2)
        project.collaborators.add(self.students[2])
        with self.assertRaises(ValidationError):
            project.submit(by=self.students[0])

    def test_cannot_submit_after_deadline(self):
        project = self.team_project()
        type(project.project_assignment).objects.filter(pk=project.project_assignment_id).update(
            deadline=timezone.now() - timedelta(hours=1)
        )
        project.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "date limite"):
            project.submit(by=self.students[0])

    def test_choice_based_requires_option(self):
        assignment = self.assignment(assignment_type="choice_based")
        project = self.project(self.students[0], assignment=assignment)
        with self.assertRaisesMessage(ValidationError, "option"):
            project.submit(by=self.students[0])
        option = ProjectOption.objects.create(assignment=assignment, title="A", description="d")
        project.selected_option = option
        project.save()
        project.submit(by=self.students[0])
        self.assertEqual(project.status, "submitted")

    def test_cannot_submit_twice_or_when_validated(self):
        project = self.team_project()
        project.submit(by=self.students[0])
        with self.assertRaises(ValidationError):
            project.submit(by=self.students[0])
        project.validate(by=self.teacher)
        with self.assertRaises(ValidationError):
            project.submit(by=self.students[0])

    def test_personal_project_can_be_submitted(self):
        project = self.project(self.students[0])
        project.submit(by=self.students[0])
        self.assertEqual(project.status, "submitted")

    # ------------------------------------------------------------ teacher side
    def test_validate(self):
        project = self.team_project()
        project.submit(by=self.students[0])
        project.validate(by=self.teacher)
        project.refresh_from_db()
        self.assertEqual(project.status, "validated")
        self.assertEqual(self.dsa_statuses(project), {"validated"})
        # whole team notified of the validation
        self.assertEqual(Notification.objects.filter(message__contains="validé").count(), 2)

    def test_reject_with_reason_resets_team_tracking(self):
        project = self.team_project()
        project.submit(by=self.students[0])
        project.reject(by=self.teacher, reason="Hors sujet")
        project.refresh_from_db()
        self.assertEqual(project.status, "rejected")
        self.assertEqual(self.dsa_statuses(project), {"started"})
        self.assertTrue(
            ProjectComment.objects.filter(project=project, content__contains="Hors sujet")
        )

    def test_request_revision_needs_message_then_allows_resubmission(self):
        project = self.team_project()
        project.submit(by=self.students[0])
        with self.assertRaises(ValidationError):
            project.request_revision(by=self.teacher, message="  ")
        project.request_revision(by=self.teacher, message="Ajoutez des tests")
        self.assertEqual(project.status, "revision_requested")
        self.assertEqual(self.dsa_statuses(project), {"started"})
        project.submit(by=self.students[0])
        self.assertEqual(project.status, "submitted")

    def test_teacher_actions_require_submitted(self):
        project = self.team_project()
        for action in (
            lambda: project.validate(by=self.teacher),
            lambda: project.reject(by=self.teacher),
            lambda: project.request_revision(by=self.teacher, message="x"),
        ):
            with self.assertRaises(ValidationError):
                action()

    # ------------------------------------------------------------------ reopen
    def test_reopen_only_rejected_and_only_owner(self):
        project = self.team_project()
        with self.assertRaises(ValidationError):
            project.reopen(by=self.students[0])
        project.submit(by=self.students[0])
        project.reject(by=self.teacher)
        with self.assertRaises(ValidationError):
            project.reopen(by=self.students[1])
        project.reopen(by=self.students[0])
        self.assertEqual(project.status, "in_progress")


class AssignmentTargetingTests(Fixtures):
    """Draft/publish targeting of direct assignments (PLAN P2.5)."""

    def test_publishing_all_students_assignment_targets_and_notifies_enrollees(self):
        from django.urls import reverse

        from student.models import Notification

        assignment = self.assignment(status="draft", target_selection="all_students")
        self.assertEqual(assignment.direct_assignments.count(), 0)
        self.login(self.teacher)
        self.client.post(reverse("teacher:assignment_publish", args=[assignment.id]))
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "published")
        self.assertEqual(assignment.direct_assignments.count(), len(self.students))
        self.assertEqual(
            Notification.objects.filter(
                project_assignment=assignment, notification_type="assignment_created"
            ).count(),
            len(self.students),
        )

    def test_reactivated_enrollment_gets_assignment_once(self):
        from teacher.models import ModuleEnrollment

        assignment = self.assignment(target_selection="all_students")
        enrollment = ModuleEnrollment.objects.get(student=self.students[0], module=self.module)
        self.assertEqual(enrollment.attach_published_assignments(), [assignment])
        self.assertEqual(enrollment.attach_published_assignments(), [])
