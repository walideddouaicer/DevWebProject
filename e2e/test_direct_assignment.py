"""Direct individual assignment + deadline reminder job."""

import io
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from student.models import Notification, Project
from teacher.models import Module, ProjectAssignment

from .base import BrowserTestCase

TITLE = "TP noté — authentification JWT"


class DirectAssignmentJourney(BrowserTestCase):
    def test_direct_individual_assignment_and_reminder(self):
        web = Module.objects.get(code="WEB401")
        student_user = web.enrollments.filter(is_active=True).order_by("-id").first().student.user

        teacher = self.as_("prof.alami")
        teacher.goto(self.url(reverse("teacher:assignment_create")))
        self.choose(self.field(teacher, "Module"), "WEB401")
        self.field(teacher, "Titre").fill(TITLE)
        self.field(teacher, "Énoncé").fill("Sécuriser l'API avec des jetons JWT.")
        self.field(teacher, "Type de devoir").select_option("direct")
        self.field(teacher, "Étudiants concernés").select_option("all_students")
        deadline = timezone.localtime() + timedelta(days=3, hours=2)
        self.field(teacher, "Date limite de rendu").fill(deadline.strftime("%Y-%m-%dT%H:%M"))
        teacher.get_by_role("button", name="Créer le brouillon").click()
        teacher.get_by_role("link", name="Publier", exact=True).click()
        teacher.get_by_role("button", name="Publier maintenant").click()
        assignment = ProjectAssignment.objects.get(title=TITLE)
        self.assertEqual(assignment.status, "published")

        # Reminder job: every enrolled student without a project gets a J-3 reminder
        out = io.StringIO()
        call_command("send_deadline_reminders", stdout=out)
        self.assertIn("rappel", out.getvalue())
        reminder = Notification.objects.filter(
            recipient__user=student_user, project_assignment=assignment
        ).last()
        self.assertIsNotNone(reminder)
        self.assertTrue(any(TITLE in m.subject for m in mail.outbox))

        # The student sees it in the notification centre, then starts the project
        student = self.as_(student_user.username)
        student.goto(self.url(reverse("student:notifications")))
        self.assertIn(TITLE, student.content())
        student.goto(self.url(reverse("student:assignment_detail", args=[assignment.id])))
        student.get_by_role("link", name="Démarrer le projet").click()
        student.get_by_role("button", name="Créer le projet").click()
        project = Project.objects.get(project_assignment=assignment, student__user=student_user)
        self.assertIn(reverse("student:project_detail", args=[project.id]), student.url)
        # Individual work: no way to invite teammates
        self.assertEqual(student.get_by_label("Inviter un étudiant").count(), 0)

        # Once the project exists, the next reminder run leaves this student alone
        call_command("send_deadline_reminders", stdout=io.StringIO())
        self.assertEqual(
            Notification.objects.filter(
                recipient__user=student_user,
                project_assignment=assignment,
                notification_type="assignment_deadline",
            ).count(),
            1,
        )
