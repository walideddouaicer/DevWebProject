"""Invitations and invite candidates (PLAN P6.4)."""

from django.urls import reverse

from teacher.models import DirectStudentAssignment

from .test_regressions import Fixtures


class InviteCandidateTests(Fixtures):
    def test_solo_project_elsewhere_does_not_empty_the_list(self):
        """Another project with no collaborators used to put NULL in NOT IN (...)."""
        s = self.students
        team = self.assignment(is_team_work=True, min_team_size=2, max_team_size=3)
        for student in s:
            DirectStudentAssignment.objects.create(assignment=team, student=student)
        mine = self.project(s[0], assignment=team)
        self.project(s[1], assignment=team)  # a solo team: no collaborators
        candidates = set(mine.invite_candidates())
        self.assertEqual(candidates, {s[2], s[3], s[4]})

    def test_candidates_respect_direct_targets_and_pending_invitations(self):
        s = self.students
        team = self.assignment(is_team_work=True, min_team_size=2, max_team_size=3)
        for student in s[:3]:
            DirectStudentAssignment.objects.create(assignment=team, student=student)
        mine = self.project(s[0], assignment=team)
        mine.invitations.create(sender=s[0], recipient=s[1])
        self.assertEqual(set(mine.invite_candidates()), {s[2]})

    def test_search_endpoint_htmx_and_owner_only(self):
        s = self.students
        project = self.project(s[0])
        url = reverse("student:invite_candidates", args=[project.id])
        self.login(s[0])
        name = s[3].user.first_name
        response = self.client.get(url, {"q": name}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Inviter")
        self.assertNotContains(response, "<html")
        full = self.client.get(url, {"q": name})
        self.assertContains(full, "<html")
        self.login(s[1])
        self.assertEqual(self.client.get(url, {"q": name}).status_code, 404)
