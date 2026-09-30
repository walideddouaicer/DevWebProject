"""The main journey: a choice-based team assignment from publication to the showcase."""

import re
import tempfile
from datetime import timedelta
from pathlib import Path

from django.urls import reverse
from django.utils import timezone

from student.models import Project, ProjectDeliverable
from teacher.models import Module, ProjectAssignment

from .base import BrowserTestCase

TITLE = "Mini-projet API météo"


class TeamAssignmentJourney(BrowserTestCase):
    def setUp(self):
        super().setUp()
        web = Module.objects.get(code="WEB401")
        # Three enrolled students who have nothing to do with the new assignment yet
        self.a, self.b, self.c = [
            e.student.user for e in web.enrollments.filter(is_active=True).order_by("id")[:3]
        ]
        self.files = Path(tempfile.mkdtemp(prefix="e2e-files-"))
        (self.files / "rapport-v1.pdf").write_bytes(b"%PDF-1.4 version 1")
        (self.files / "rapport-v2.pdf").write_bytes(b"%PDF-1.4 version 2")

    def step_teacher_creates_and_publishes(self):
        teacher = self.as_("prof.alami")
        teacher.get_by_role("link", name="Nouveau devoir").first.click()
        self.choose(self.field(teacher, "Module"), "WEB401")
        self.field(teacher, "Titre").fill(TITLE)
        self.field(teacher, "Énoncé").fill("Construire une API REST de données météo.")
        self.field(teacher, "Type de devoir").select_option("choice_based")
        self.field(teacher, "Travail en équipe").check()
        self.field(teacher, "Taille minimale").fill("2")
        self.field(teacher, "Taille maximale").fill("3")
        deadline = timezone.localtime() + timedelta(days=30)
        self.field(teacher, "Date limite de rendu").fill(deadline.strftime("%Y-%m-%dT18:00"))
        teacher.get_by_role("button", name="Créer le brouillon").click()

        # Subjects page
        self.field(teacher, "Titre").fill("Sujet A — capteurs LoRa")
        self.field(teacher, "Description").fill("Collecter et exposer des mesures.")
        teacher.get_by_role("button", name="Ajouter").click()
        teacher.get_by_role("link", name="Publier le devoir").click()
        teacher.get_by_role("button", name="Publier maintenant").click()
        assignment = ProjectAssignment.objects.get(title=TITLE)
        self.assertEqual(assignment.status, "published")
        return teacher, assignment

    def step_student_picks_subject(self, assignment):
        a = self.as_(self.a.username)
        a.goto(self.url(reverse("student:assignments_dashboard")))
        a.get_by_role("link", name=TITLE).first.click()
        a.get_by_role("link", name="Choisir un sujet").click()
        a.get_by_label(re.compile("Sujet A")).check()
        a.get_by_role("button", name="Continuer avec ce sujet").click()
        self.field(a, "Titre").fill("Équipe Atlas")
        a.get_by_role("button", name="Créer le projet").click()
        project = Project.objects.get(project_assignment=assignment, student__user=self.a)
        self.assertIn(reverse("student:project_detail", args=[project.id]), a.url)
        return a, project

    def step_team_forms(self, a, project):
        for mate in (self.b, self.c):
            self.choose(a.get_by_label("Inviter un étudiant"), mate.get_full_name())
            a.get_by_role("button", name="Envoyer l'invitation").click()
            self.assertIn("Invitation envoyée", " ".join(self.toast(a)))
        for mate in (self.b, self.c):
            page = self.as_(mate.username)
            page.goto(self.url(reverse("student:invitations_list")))
            page.get_by_role("button", name="Accepter").first.click()
            self.assertIn(reverse("student:project_detail", args=[project.id]), page.url)
        self.assertEqual(project.collaborators.count(), 2)

    def upload(self, page, project, filename):
        page.goto(self.url(reverse("student:upload_deliverable", args=[project.id])))
        page.locator("input[type=file]").set_input_files(self.files / filename)
        self.field(page, "Nom du livrable").fill("Rapport final")
        self.field(page, "Type").select_option("report")
        page.get_by_role("button", name="Déposer").click()

    def test_choice_based_team_assignment_end_to_end(self):
        teacher, assignment = self.step_teacher_creates_and_publishes()
        a, project = self.step_student_picks_subject(assignment)
        self.step_team_forms(a, project)

        # Two versions of the same deliverable
        self.upload(a, project, "rapport-v1.pdf")
        self.upload(a, project, "rapport-v2.pdf")
        versions = ProjectDeliverable.objects.filter(project=project, name="Rapport final")
        self.assertEqual(sorted(versions.values_list("version", flat=True)), [1, 2])

        # Submit, teacher asks for a revision, resubmit
        def submit():
            a.goto(self.url(reverse("student:project_detail", args=[project.id])))
            a.get_by_role("link", name="Soumettre").click()
            a.get_by_role("button", name="Soumettre maintenant").click()

        submit()
        teacher.goto(self.url(reverse("teacher:project_review", args=[project.id])))
        teacher.get_by_text("Demander une révision").click()
        teacher.get_by_label("Modifications attendues").fill("Ajoutez la documentation OpenAPI.")
        teacher.get_by_role("button", name="Envoyer la demande").click()
        project.refresh_from_db()
        self.assertEqual(project.status, "revision_requested")
        a.goto(self.url(reverse("student:project_detail", args=[project.id])))
        self.assertIn("Ajoutez la documentation OpenAPI.", a.content())
        submit()

        # Grade + validate in one go
        teacher.goto(self.url(reverse("teacher:grade_project", args=[project.id])))
        self.field(teacher, "Note sur 20").fill("16,5")
        self.field(teacher, "Appréciation").fill("Très bonne API, tests solides.")
        teacher.get_by_role("button", name="Enregistrer la note").click()
        project.refresh_from_db()
        self.assertEqual(project.status, "validated")
        self.assertEqual(str(project.evaluation.score), "16.50")

        # Publish on the showcase
        a.goto(self.url(reverse("student:make_project_public", args=[project.id])))
        self.field(a, "Description publique").fill("Une API météo ouverte, construite en équipe.")
        a.get_by_role("button", name="Publier").click()
        project.refresh_from_db()
        self.assertTrue(project.is_public)

        # A visitor sees it; liking and reporting require an account
        visitor = self.page()
        public_url = self.url(reverse("public:project_detail", args=[project.id]))
        visitor.goto(self.url(reverse("public:projects_showcase")))
        visitor.get_by_role("link", name="Équipe Atlas").first.click()
        self.assertIn("Une API météo ouverte", visitor.content())
        visitor.get_by_role("link", name=re.compile("J'aime")).click()
        self.assertIn("/login/?next=", visitor.url)
        visitor.goto(self.url(reverse("public:report_project", args=[project.id])))
        self.assertIn("/login/", visitor.url)

        # Another student reports it; the admin hides it
        reporter = self.as_("etu.anas")
        reporter.goto(self.url(reverse("public:report_project", args=[project.id])))
        self.field(reporter, "Motif").select_option(index=1)
        self.field(reporter, "Précisions").fill("Contenu copié d'un autre dépôt.")
        reporter.get_by_role("button", name="Envoyer le signalement").click()

        admin = self.as_("admin")
        admin.goto(self.url(reverse("administrator:reports_moderation") + "?show=all"))
        card = admin.locator("article").filter(has_text="Équipe Atlas")
        card.get_by_label("Note interne").fill("Signalement vérifié.")
        card.get_by_role("button", name="Masquer").click()
        project.refresh_from_db()
        self.assertTrue(project.is_hidden_by_admin)
        self.expected_console.append("status of 404")
        response = visitor.goto(public_url)
        self.assertEqual(response.status, 404)
