"""Team building: invite → accept/decline/cancel → remove; milestones (PLAN P7.1)."""

from django.core import mail
from django.core.exceptions import ValidationError
from django.urls import reverse

from student.models import (
    CollaborationInvitation,
    Notification,
    ProjectActivity,
    ProjectMilestone,
    StudentProfile,
    TeammateRequest,
)
from teacher.models import DirectStudentAssignment

from .test_regressions import Fixtures


class InviteTests(Fixtures):
    def setUp(self):
        self.owner, self.mate, self.third = self.students[:3]
        self.assignment_ = self.assignment(
            is_team_work=True, min_team_size=2, max_team_size=2, assignment_type="choice"
        )
        self.project_ = self.project(self.owner, assignment=self.assignment_)

    def invite(self, recipient, by=None):
        self.login(by or self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("student:add_collaborator", args=[self.project_.id]),
                {"collaborator": recipient.id},
                follow=True,
            )

    def test_invite_creates_invitation_notification_and_email(self):
        response = self.invite(self.mate)
        self.assertContains(response, "Invitation envoyée")
        invitation = CollaborationInvitation.objects.get()
        self.assertEqual((invitation.sender, invitation.recipient), (self.owner, self.mate))
        notification = Notification.objects.get(recipient=self.mate)
        self.assertIn(self.assignment_.title, notification.message)
        self.assertEqual(mail.outbox[0].to, [self.mate.user.email])

    def test_duplicate_pending_invitation_is_refused(self):
        self.invite(self.mate)
        response = self.invite(self.mate)
        self.assertContains(response, "déjà été envoyée")
        self.assertEqual(Notification.objects.filter(recipient=self.mate).count(), 1)

    def test_declined_invitation_can_be_renewed(self):
        self.invite(self.mate)
        CollaborationInvitation.objects.update(status="rejected")
        self.invite(self.mate)
        self.assertEqual(CollaborationInvitation.objects.get().status, "pending")

    def test_only_owner_can_invite(self):
        self.project_.collaborators.add(self.mate)
        response = self.invite(self.third, by=self.mate)
        self.assertEqual(response.status_code, 404)

    def test_full_team_refuses_invitations(self):
        self.project_.collaborators.add(self.mate)
        with self.assertRaisesMessage(ValidationError, "taille maximale"):
            self.project_.invite(by=self.owner, recipient=self.third)

    def test_submitted_project_refuses_invitations(self):
        self.project_.status = "submitted"
        self.project_.save()
        with self.assertRaisesMessage(ValidationError, "projet en cours"):
            self.project_.invite(by=self.owner, recipient=self.third)

    def test_individual_assignment_refuses_invitations(self):
        self.assignment_.is_team_work = False
        self.assignment_.save()
        with self.assertRaisesMessage(ValidationError, "individuellement"):
            self.project_.invite(by=self.owner, recipient=self.mate)

    def test_cannot_invite_self_or_existing_member(self):
        with self.assertRaisesMessage(ValidationError, "fait déjà partie"):
            self.project_.invite(by=self.owner, recipient=self.owner)

    def test_direct_assignment_requires_target(self):
        direct = self.assignment(
            is_team_work=True, min_team_size=2, max_team_size=3, assignment_type="direct"
        )
        project = self.project(self.owner, assignment=direct)
        with self.assertRaisesMessage(ValidationError, "pas assigné"):
            project.invite(by=self.owner, recipient=self.mate)
        DirectStudentAssignment.objects.create(assignment=direct, student=self.mate)
        with self.captureOnCommitCallbacks():
            project.invite(by=self.owner, recipient=self.mate)

    def test_unknown_student_is_404(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("student:add_collaborator", args=[self.project_.id]), {"collaborator": 9999}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_is_not_allowed(self):
        self.login(self.owner)
        response = self.client.get(reverse("student:add_collaborator", args=[self.project_.id]))
        self.assertEqual(response.status_code, 405)


class RespondTests(Fixtures):
    def setUp(self):
        self.owner, self.mate, self.third = self.students[:3]
        self.assignment_ = self.assignment(
            is_team_work=True, min_team_size=2, max_team_size=2, assignment_type="choice"
        )
        self.project_ = self.project(self.owner, assignment=self.assignment_)
        with self.captureOnCommitCallbacks():
            self.invitation = self.project_.invite(by=self.owner, recipient=self.mate)

    def respond(self, response, invitation=None, as_=None):
        self.login(as_ or self.mate)
        invitation = invitation or self.invitation
        return self.client.post(
            reverse("student:respond_to_invitation", args=[invitation.id, response])
        )

    def test_accept_joins_team_and_notifies_owner(self):
        TeammateRequest.objects.create(assignment=self.assignment_, student=self.mate)
        response = self.respond("accept")
        self.assertRedirects(response, reverse("student:project_detail", args=[self.project_.id]))
        self.assertIn(self.mate, self.project_.collaborators.all())
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "accepted")
        self.assertFalse(TeammateRequest.objects.get().is_active)
        self.assertTrue(Notification.objects.filter(recipient=self.owner).exists())
        self.assertTrue(ProjectActivity.objects.filter(activity_type="collaborator_added").exists())

    def test_accept_when_team_became_full_closes_invitation(self):
        with self.captureOnCommitCallbacks():
            other = self.project_.invite(by=self.owner, recipient=self.third)
        self.respond("accept")  # team is now 2/2
        response = self.respond("accept", invitation=other, as_=self.third)
        self.assertRedirects(response, reverse("student:invitations_list"))
        other.refresh_from_db()
        self.assertEqual(other.status, "rejected")
        self.assertNotIn(self.third, self.project_.collaborators.all())

    def test_decline(self):
        self.respond("reject")
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "rejected")
        self.assertNotIn(self.mate, self.project_.collaborators.all())

    def test_only_recipient_can_respond(self):
        self.assertEqual(self.respond("accept", as_=self.third).status_code, 404)

    def test_answered_invitation_cannot_be_reused(self):
        self.respond("reject")
        self.assertEqual(self.respond("accept").status_code, 404)
        self.invitation.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.invitation.accept()

    def test_sender_can_cancel(self):
        self.login(self.owner)
        self.client.post(reverse("student:cancel_invitation", args=[self.invitation.id]))
        self.assertFalse(CollaborationInvitation.objects.exists())

    def test_invitations_page_lists_both_directions(self):
        self.login(self.mate)
        self.assertContains(
            self.client.get(reverse("student:invitations_list")), self.project_.title
        )
        self.login(self.owner)
        self.assertContains(
            self.client.get(reverse("student:invitations_list")), self.mate.get_full_name()
        )


class RemoveCollaboratorTests(Fixtures):
    def test_owner_removes_member_within_team_rules(self):
        owner, mate, third = self.students[:3]
        assignment = self.assignment(
            is_team_work=True, min_team_size=2, max_team_size=3, assignment_type="choice"
        )
        project = self.project(owner, [mate, third], assignment=assignment)
        self.login(owner)
        url = reverse("student:remove_collaborator", args=[project.id, third.id])
        self.client.post(url)
        self.assertNotIn(third, project.collaborators.all())
        # Now at the minimum: removing another member is refused
        self.client.post(reverse("student:remove_collaborator", args=[project.id, mate.id]))
        self.assertIn(mate, project.collaborators.all())

    def test_member_cannot_remove(self):
        owner, mate = self.students[:2]
        project = self.project(owner, [mate])
        self.login(mate)
        response = self.client.post(
            reverse("student:remove_collaborator", args=[project.id, mate.id])
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn(mate, project.collaborators.all())


class MilestoneTests(Fixtures):
    def setUp(self):
        self.owner, self.mate, self.outsider = self.students[:3]
        self.project_ = self.project(self.owner, [self.mate])

    def test_member_adds_and_toggles_milestone(self):
        self.login(self.mate)
        url = reverse("student:add_milestone", args=[self.project_.id])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"title": "Maquettes", "due_date": "2026-11-01"})
        milestone = ProjectMilestone.objects.get(project=self.project_)
        toggle = reverse("student:toggle_milestone", args=[milestone.id])
        self.client.post(toggle)
        milestone.refresh_from_db()
        self.assertTrue(milestone.completed)
        self.assertEqual(milestone.completed_by, self.mate.user)
        self.client.post(toggle)
        milestone.refresh_from_db()
        self.assertFalse(milestone.completed)
        self.assertIsNone(milestone.completed_at)

    def test_invalid_milestone_rerenders_form(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("student:add_milestone", args=[self.project_.id]), {"title": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProjectMilestone.objects.exists())

    def test_outsider_cannot_touch_milestones(self):
        milestone = ProjectMilestone.objects.create(
            project=self.project_, title="J1", due_date="2026-11-01"
        )
        self.login(self.outsider)
        self.assertEqual(
            self.client.post(reverse("student:toggle_milestone", args=[milestone.id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("student:add_milestone", args=[self.project_.id])).status_code,
            404,
        )
        self.assertEqual(StudentProfile.objects.count(), 5)
