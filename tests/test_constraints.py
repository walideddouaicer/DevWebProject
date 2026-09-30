"""Database constraints (PLAN P2.10): invalid rows are rejected even if code forgets to check."""

from decimal import Decimal

from django.db import IntegrityError, transaction

from teacher.models import ProjectAssignment, ProjectEvaluation, ProjectOption

from .test_regressions import Fixtures


class ConstraintTests(Fixtures):
    def test_team_sizes(self):
        assignment = self.assignment()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectAssignment.objects.filter(pk=assignment.pk).update(
                min_team_size=3, max_team_size=2
            )

    def test_option_counters(self):
        option = ProjectOption.objects.create(
            assignment=self.assignment(assignment_type="choice_based"), title="A", description="d"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectOption.objects.filter(pk=option.pk).update(current_teams=-1)

    def test_score_range(self):
        project = self.project(self.students[0], status="submitted")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectEvaluation.objects.create(
                project=project, teacher=self.teacher, score=Decimal(25)
            )
