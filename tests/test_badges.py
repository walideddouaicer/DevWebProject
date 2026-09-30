"""Navigation badges (PLAN P3.4): always exact, per role."""

from django.test import RequestFactory

from accounts.context_processors import badges
from student.models import CollaborationInvitation, Notification

from .test_regressions import Fixtures


class BadgeTests(Fixtures):
    def context_for(self, profile):
        request = RequestFactory().get("/")
        request.user = type(profile.user).objects.get(pk=profile.user_id)
        return badges(request)

    def test_student_badges_update_immediately(self):
        student = self.students[0]
        self.assertEqual(self.context_for(student)["unread_notifications_count"], 0)
        Notification.objects.create(
            recipient=student, notification_type="project_update", message="x"
        )
        CollaborationInvitation.objects.create(
            project=self.project(self.students[1]), sender=self.students[1], recipient=student
        )
        context = self.context_for(student)
        self.assertEqual(context["unread_notifications_count"], 1)
        self.assertEqual(context["invitation_count"], 1)
        self.assertEqual(context["user_role"], "student")

    def test_teacher_sees_projects_to_review_in_own_modules_only(self):
        self.project(self.students[0], status="submitted")
        self.project(self.students[1], status="submitted", module=None)
        self.assertEqual(self.context_for(self.teacher)["ungraded_projects_count"], 1)
        self.assertEqual(self.context_for(self.other_teacher)["ungraded_projects_count"], 0)

    def test_admin_badges(self):
        context = self.context_for(self.admin)
        self.assertEqual(context["user_role"], "admin")
        self.assertIn("pending_registrations_count", context)
