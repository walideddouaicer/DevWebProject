"""Populate the database with realistic demo data (PLAN P0.5).

    python manage.py seed_demo            # no-op if demo data already exists
    python manage.py seed_demo --reset    # wipe the WHOLE database, then seed (DEBUG only)

All demo accounts share the password DEMO_PASSWORD. Data is deterministic (fixed RNG
seed) so screenshots and smoke tests are stable. Dates are relative to "now" so the
demo always has upcoming and overdue deadlines.
"""

import io
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import PendingRegistration
from administrator.models import AdminProfile
from student.models import (
    CollaborationInvitation,
    DeliverableComment,
    Notification,
    Project,
    ProjectActivity,
    ProjectComment,
    ProjectDeliverable,
    ProjectLike,
    ProjectMilestone,
    ProjectReport,
    ProjectShowcaseTag,
    PublicProjectComment,
    ShowcaseTag,
    StudentProfile,
    TeammateRequest,
    UserPreferences,
)
from teacher.models import (
    DirectStudentAssignment,
    EvaluationCriterion,
    Module,
    ModuleAnnouncement,
    ModuleAssignment,
    ModuleEnrollment,
    ProjectAssignment,
    ProjectEvaluation,
    ProjectOption,
    TeacherProfile,
)

DEMO_PASSWORD = "demo12345!"
EMAIL_DOMAIN = "demo.ensa.local"

TEACHERS = [
    ("prof.alami", "Karim", "Alami", "ENS-101", "Génie Informatique"),
    ("prof.bennani", "Nadia", "Bennani", "ENS-102", "Génie Informatique"),
    ("prof.elidrissi", "Omar", "El Idrissi", "ENS-201", "Génie Électrique"),
    ("prof.tazi", "Leila", "Tazi", "ENS-301", "Génie Industriel"),
]

# Named students first (used as stable demo logins), then the rest of the cohort.
STUDENTS = [
    ("etu.amine", "Amine", "Berrada", 4, "Génie Informatique"),
    ("etu.salma", "Salma", "Chraibi", 4, "Génie Informatique"),
    ("etu.youssef", "Youssef", "Ouazzani", 4, "Génie Informatique"),
    ("etu.imane", "Imane", "Lahlou", 4, "Génie Informatique"),
    ("etu.mehdi", "Mehdi", "Fassi", 4, "Génie Informatique"),
    ("etu.hajar", "Hajar", "Benjelloun", 4, "Génie Informatique"),
    ("etu.reda", "Reda", "Tahiri", 4, "Génie Informatique"),
    ("etu.kenza", "Kenza", "Amrani", 4, "Génie Informatique"),
    ("etu.anas", "Anas", "Zniber", 4, "Génie Informatique"),
    ("etu.meryem", "Meryem", "Sqalli", 4, "Génie Informatique"),
    ("etu.hamza", "Hamza", "Kettani", 5, "Génie Informatique"),
    ("etu.sara", "Sara", "Idrissi", 5, "Génie Informatique"),
    ("etu.othmane", "Othmane", "Bennis", 5, "Génie Informatique"),
    ("etu.ghita", "Ghita", "Alaoui", 5, "Génie Informatique"),
    ("etu.ilyas", "Ilyas", "Sefrioui", 5, "Génie Informatique"),
    ("etu.nour", "Nour", "Hajji", 5, "Génie Informatique"),
    ("etu.zakaria", "Zakaria", "Moussaoui", 4, "Génie Électrique"),
    ("etu.wiam", "Wiam", "Rami", 4, "Génie Électrique"),
    ("etu.ayoub", "Ayoub", "Filali", 4, "Génie Électrique"),
    ("etu.chaimae", "Chaimae", "Naciri", 4, "Génie Électrique"),
    ("etu.adam", "Adam", "Skalli", 3, "Génie Industriel"),
    ("etu.lina", "Lina", "Bouzidi", 3, "Génie Industriel"),
    ("etu.soufiane", "Soufiane", "Jettou", 3, "Génie Industriel"),
    ("etu.douae", "Douae", "Kabbaj", 3, "Génie Industriel"),
    ("etu.ismail", "Ismail", "Guessous", 3, "Génie Industriel"),
    ("etu.yasmine", "Yasmine", "Lamrani", 5, "Génie Informatique"),
    ("etu.badr", "Badr", "Cherkaoui", 5, "Génie Informatique"),
    ("etu.rania", "Rania", "Mernissi", 4, "Génie Informatique"),
    ("etu.saad", "Saad", "Bouhaddou", 4, "Génie Électrique"),
    ("etu.khadija", "Khadija", "Tounsi", 3, "Génie Industriel"),
]

MODULES = [
    # code, name, teachers (usernames), description, semester, classroom
    (
        "WEB401",
        "Développement web avancé",
        ["prof.alami"],
        "Architecture d'applications web, Django, API REST, déploiement.",
        "S1",
        "Salle B12",
    ),
    (
        "BDD402",
        "Bases de données avancées",
        ["prof.bennani"],
        "Modélisation, optimisation de requêtes, transactions et NoSQL.",
        "S1",
        "Salle B04",
    ),
    (
        "IA501",
        "Intelligence artificielle appliquée",
        ["prof.alami", "prof.bennani"],
        "Apprentissage supervisé, évaluation de modèles, projets appliqués.",
        "S2",
        "Amphi 2",
    ),
    (
        "SEM402",
        "Systèmes embarqués",
        ["prof.elidrissi"],
        "Microcontrôleurs, temps réel, capteurs et IoT.",
        "S1",
        "Labo électronique",
    ),
    (
        "LOG301",
        "Logistique et chaîne d'approvisionnement",
        ["prof.tazi"],
        "Gestion des stocks, planification et simulation de flux.",
        "S2",
        "Salle A07",
    ),
]

TAGS = [
    ("Web", "#1F5C57"),
    ("Data", "#2B4F7A"),
    ("IA", "#6B4E9A"),
    ("IoT", "#8A5A00"),
    ("Mobile", "#2E6B3A"),
    ("Industrie", "#A8321E"),
]


def make_pdf(title, subtitle):
    """A tiny but valid one-page PDF for demo deliverables."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, 760, title[:70])
    pdf.setFont("Helvetica", 11)
    pdf.drawString(72, 736, subtitle[:90])
    pdf.drawString(72, 712, "Document de démonstration — ENSA Project Manager")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Crée des données de démonstration réalistes (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Vide TOUTE la base puis la remplit (refusé si DEBUG=False).",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            if not settings.DEBUG:
                raise CommandError("--reset est interdit quand DEBUG=False.")
            call_command("flush", interactive=False, verbosity=0)
        elif User.objects.filter(username="admin").exists():
            self.stdout.write("Données de démonstration déjà présentes (utilisez --reset).")
            return

        self.rng = random.Random(42)
        self.now = timezone.now()
        self.today = timezone.localdate()
        self.password_hash = make_password(DEMO_PASSWORD)

        with transaction.atomic():
            self.seed()

        self.stdout.write(
            self.style.SUCCESS(
                f"Démo prête: {User.objects.count()} utilisateurs, {Project.objects.count()} projets. "
                f"Mot de passe commun: {DEMO_PASSWORD}"
            )
        )

    # ------------------------------------------------------------------ helpers

    def user(self, username, first, last, **extra):
        email = f"{username.replace('.', '_')}@{EMAIL_DOMAIN}"
        user = User.objects.create(
            username=username,
            first_name=first,
            last_name=last,
            email=email,
            password=self.password_hash,
            **extra,
        )
        return user

    def days(self, n):
        return self.now + timedelta(days=n)

    def create_assignment(self, deadline_days, selection_days=None, **fields):
        """ProjectAssignment.clean() refuses past deadlines at creation, so create in the
        future and move dates afterwards."""
        assignment = ProjectAssignment.objects.create(
            deadline=self.days(60),
            selection_deadline=self.days(30) if selection_days is not None else None,
            **fields,
        )
        updates = {"deadline": self.days(deadline_days)}
        if selection_days is not None:
            updates["selection_deadline"] = self.days(selection_days)
        if fields.get("status") in ("published", "completed", "in_progress"):
            updates["published_at"] = self.days(min(deadline_days, 0) - 20)
        ProjectAssignment.objects.filter(pk=assignment.pk).update(**updates)
        assignment.refresh_from_db()
        return assignment

    def project(self, owner, title, description, members=(), **fields):
        fields.setdefault("project_type", "module")
        fields.setdefault("start_date", self.today - timedelta(days=self.rng.randint(15, 60)))
        fields.setdefault("technologies", "")
        project = Project.objects.create(
            student=owner, title=title, description=description, **fields
        )
        if members:
            project.collaborators.add(*members)
        ProjectActivity.objects.create(
            project=project,
            user=owner.user,
            activity_type="assignment_created" if project.project_assignment_id else "created",
            description="Projet créé",
        )
        for member in members:
            ProjectActivity.objects.create(
                project=project,
                user=member.user,
                activity_type="collaborator_added",
                description=f"{member.get_full_name()} a rejoint le projet",
            )
        return project

    def deliverable(self, project, name, file_type, versions=1, uploader=None):
        uploader = uploader or project.student
        items = []
        for version in range(1, versions + 1):
            deliverable = ProjectDeliverable(
                project=project, name=name, file_type=file_type, version=version
            )
            slug = name.lower().replace(" ", "_").replace("'", "")[:40]
            deliverable.file.save(
                f"{slug}_v{version}.pdf",
                ContentFile(make_pdf(name, f"{project.title} — version {version}")),
                save=True,
            )
            ProjectActivity.objects.create(
                project=project,
                user=uploader.user,
                activity_type="deliverable_added",
                description=f"Livrable ajouté: {name}" + (f" (v{version})" if version > 1 else ""),
            )
            items.append(deliverable)
        return items

    def milestones(self, project, specs):
        for title, offset_days, done in specs:
            ProjectMilestone.objects.create(
                project=project,
                title=title,
                due_date=self.today + timedelta(days=offset_days),
                completed=done,
                completed_by=project.student.user if done else None,
                completed_at=self.days(offset_days - 1) if done else None,
            )

    def evaluate(self, project, teacher, score, comments, criteria):
        evaluation = ProjectEvaluation.objects.create(
            project=project, teacher=teacher, score=Decimal(score), comments=comments
        )
        for order, (name, crit_score, comment) in enumerate(criteria):
            EvaluationCriterion.objects.create(
                evaluation=evaluation,
                name=name,
                score=Decimal(crit_score),
                comment=comment,
                order=order,
            )
        return evaluation

    def notify(
        self, students, message, kind="project_update", project=None, assignment=None, read=False
    ):
        for student in students:
            Notification.objects.create(
                recipient=student,
                project=project,
                project_assignment=assignment,
                notification_type=kind,
                message=message,
                is_read=read,
            )

    def make_public(self, project, tags, cover_desc, demo="", github="", views=0):
        project.is_public = True
        project.made_public_at = self.days(-self.rng.randint(2, 40))
        project.public_description = cover_desc
        project.public_demo_url = demo
        project.public_github_url = github
        project.view_count = views
        project.save()
        for tag in tags:
            ProjectShowcaseTag.objects.create(project=project, tag=self.tags[tag])

    # ------------------------------------------------------------------ seed

    def seed(self):
        # --- People
        admin_user = self.user("admin", "Fatima", "Zahra Ennaji")
        AdminProfile.objects.create(
            user=admin_user, admin_id="ADM-001", role="Responsable scolarité"
        )

        self.teachers = {}
        for username, first, last, teacher_id, department in TEACHERS:
            self.teachers[username] = TeacherProfile.objects.create(
                user=self.user(username, first, last),
                teacher_id=teacher_id,
                department=department,
            )

        self.students = {}
        for index, (username, first, last, year, department) in enumerate(STUDENTS, start=1):
            self.students[username] = StudentProfile.objects.create(
                user=self.user(username, first, last),
                student_id=f"E{2021 + (5 - year)}{index:03d}",
                year_of_study=year,
                department=department,
                bio=(
                    "Passionné(e) par le développement logiciel et les projets d'équipe."
                    if index % 3 == 0
                    else None
                ),
                github_url=f"https://github.com/{username.split('.')[1]}-demo"
                if index % 2 == 0
                else None,
            )
            UserPreferences.objects.create(
                user=self.students[username].user,
                email_digest=(index % 5 == 0),
                theme_preference="auto",
            )
        s = self.students

        # --- Modules, teaching assignments, enrollments
        self.modules = {}
        for code, name, teachers, description, semester, classroom in MODULES:
            module = Module.objects.create(
                code=code,
                name=name,
                description=description,
                academic_year="2026-2027",
                semester=semester,
                classroom=classroom,
                primary_teacher=self.teachers[teachers[0]],
            )
            for teacher in teachers:
                ModuleAssignment.objects.create(
                    teacher=self.teachers[teacher], module=module, assigned_by=admin_user
                )
            self.modules[code] = module
        m = self.modules

        info_4 = [p for p in s.values() if p.year_of_study == 4 and "Informatique" in p.department]
        info_5 = [p for p in s.values() if p.year_of_study == 5]
        elec = [p for p in s.values() if "Électrique" in p.department]
        indus = [p for p in s.values() if "Industriel" in p.department]
        for student in info_4:
            ModuleEnrollment.objects.create(student=student, module=m["WEB401"])
            ModuleEnrollment.objects.create(student=student, module=m["BDD402"])
        for student in info_5:
            ModuleEnrollment.objects.create(student=student, module=m["IA501"])
        for student in elec:
            ModuleEnrollment.objects.create(student=student, module=m["SEM402"])
        for student in indus:
            ModuleEnrollment.objects.create(student=student, module=m["LOG301"])
        # A student who left a module (inactive enrollment)
        ModuleEnrollment.objects.create(student=s["etu.hamza"], module=m["WEB401"], is_active=False)

        self.tags = {
            name: ShowcaseTag.objects.create(name=name, color=color) for name, color in TAGS
        }

        self.seed_web401(m["WEB401"])
        self.seed_bdd402(m["BDD402"], info_4)
        self.seed_ia501(m["IA501"])
        self.seed_sem402(m["SEM402"])
        self.seed_log301(m["LOG301"], indus)
        self.seed_personal_projects()
        self.seed_social()
        self.seed_registrations()

        ModuleAnnouncement.objects.create(
            module=m["WEB401"],
            teacher=self.teachers["prof.alami"],
            title="Soutenances intermédiaires",
            content=(
                "Les soutenances intermédiaires auront lieu la semaine prochaine en salle B12. "
                "Préparez une démo de 10 minutes et un état d'avancement."
            ),
        )
        ModuleAnnouncement.objects.create(
            module=m["IA501"],
            teacher=self.teachers["prof.bennani"],
            title="Jeux de données disponibles",
            content="Les jeux de données du projet sont disponibles sur le serveur du département.",
        )
        self.notify(
            [p for p in s.values() if p.year_of_study == 4 and "Informatique" in p.department],
            "[WEB401] Soutenances intermédiaires — Les soutenances auront lieu la semaine prochaine.",
            kind="announcement",
        )

    def seed_web401(self, module):
        s = self.students
        alami = self.teachers["prof.alami"]
        assignment = self.create_assignment(
            deadline_days=25,
            selection_days=5,
            teacher=alami,
            module=module,
            title="Projet de fin de module — application web",
            description=(
                "Concevoir et déployer une application web complète répondant à un besoin réel "
                "d'une association ou d'une PME de la région."
            ),
            instructions=(
                "Équipes de 2 à 3. Livrables: cahier des charges, maquettes, code source, "
                "rapport final et démo."
            ),
            assignment_type="choice_based",
            is_team_work=True,
            min_team_size=2,
            max_team_size=3,
            status="published",
        )
        options = [
            ("Plateforme de réservation pour un riad", "hard", True, 1),
            ("Gestion des adhérents d'une association sportive", "medium", True, 1),
            ("Tableau de bord de suivi des stages", "medium", False, 2),
            ("Marketplace de produits de coopératives", "hard", True, 1),
            ("Application de covoiturage étudiant", "easy", True, 1),
        ]
        opts = []
        for order, (title, difficulty, unique, max_teams) in enumerate(options, start=1):
            opts.append(
                ProjectOption.objects.create(
                    assignment=assignment,
                    title=title,
                    description=f"{title}: analyse du besoin, conception, réalisation et tests.",
                    requirements="Django ou équivalent, base relationnelle, tests automatisés.",
                    estimated_difficulty=difficulty,
                    is_unique=unique,
                    max_teams=max_teams,
                    order=order,
                )
            )

        def team(owner, members, option, status, **extra):
            project = self.project(
                owner,
                option.title,
                option.description,
                members=members,
                assignment_source="teacher_assigned",
                project_assignment=assignment,
                selected_option=option,
                assignment_deadline=assignment.deadline,
                module=module,
                status=status,
                technologies="Django, PostgreSQL, HTMX",
                end_date=assignment.deadline.date(),
                **extra,
            )
            option.current_teams += 1
            option.save(update_fields=["current_teams"])
            return project

        # Amine + Salma: in progress, with versioned deliverables and feedback
        p1 = team(s["etu.amine"], [s["etu.salma"]], opts[0], "in_progress")
        cdc = self.deliverable(p1, "Cahier des charges", "report", versions=2)
        self.deliverable(p1, "Maquettes", "presentation", uploader=s["etu.salma"])
        DeliverableComment.objects.create(
            deliverable=cdc[0],
            author=self.teachers["prof.alami"].user,
            content="Précisez les rôles utilisateurs et les cas d'usage prioritaires.",
        )
        DeliverableComment.objects.create(
            deliverable=cdc[0],
            author=s["etu.amine"].user,
            content="C'est corrigé dans la v2, section 3.",
        )
        self.milestones(
            p1,
            [
                ("Cahier des charges validé", -12, True),
                ("Maquettes haute fidélité", -3, True),
                ("MVP réservation", 6, False),
                ("Tests et déploiement", 20, False),
            ],
        )
        ProjectComment.objects.create(
            project=p1,
            author=s["etu.salma"].user,
            content="J'ai poussé les maquettes, il reste la page de paiement.",
        )
        # Pending invitation to a third member
        CollaborationInvitation.objects.create(
            project=p1, sender=s["etu.amine"], recipient=s["etu.mehdi"], message="Rejoins-nous !"
        )
        self.notify(
            [s["etu.mehdi"]],
            f"Amine Berrada vous invite à collaborer sur le projet '{p1.title}'",
            kind="invitation",
            project=p1,
            assignment=assignment,
        )

        # Youssef + Imane + Hajar: submitted, awaiting review
        p2 = team(
            s["etu.youssef"],
            [s["etu.imane"], s["etu.hajar"]],
            opts[1],
            "submitted",
            assignment_submitted_at=self.days(-1),
        )
        self.deliverable(p2, "Rapport final", "report")
        self.deliverable(p2, "Code source", "source_code", uploader=s["etu.imane"])
        self.milestones(p2, [("Analyse", -20, True), ("Développement", -5, True)])

        # Reda + Kenza: revision requested
        p3 = team(s["etu.reda"], [s["etu.kenza"]], opts[2], "revision_requested")
        self.deliverable(p3, "Rapport final", "report", versions=1)
        ProjectComment.objects.create(
            project=p3,
            author=alami.user,
            content="[RÉVISION DEMANDÉE]\nAjoutez une section sur les tests et la sécurité.",
        )
        self.notify(
            [s["etu.reda"], s["etu.kenza"]],
            f"Karim Alami demande des révisions sur le projet '{p3.title}'.",
            project=p3,
            assignment=assignment,
        )

        # Teamless students looking for a team
        for username, message in [
            ("etu.anas", "Back-end Django, disponible le soir."),
            ("etu.meryem", "UI/UX et front-end, j'ai déjà fait des maquettes Figma."),
        ]:
            TeammateRequest.objects.create(
                assignment=assignment, student=s[username], message=message
            )

        # Draft assignment (not visible to students)
        self.create_assignment(
            deadline_days=50,
            teacher=alami,
            module=module,
            title="Mini-projet API REST",
            description="Exposer une API documentée pour l'application du module.",
            assignment_type="direct",
            target_selection="all_students",
            status="draft",
        )

    def seed_bdd402(self, module, cohort):
        s = self.students
        bennani = self.teachers["prof.bennani"]
        assignment = self.create_assignment(
            deadline_days=3,
            teacher=bennani,
            module=module,
            title="TP noté — optimisation de requêtes",
            description="Analyser et optimiser un jeu de requêtes lentes sur une base fournie.",
            instructions="Travail individuel. Rendre un rapport PDF et les scripts SQL.",
            assignment_type="direct",
            target_selection="all_students",
            status="published",
        )
        for student in cohort:
            DirectStudentAssignment.objects.create(assignment=assignment, student=student)

        def solo(student, status):
            project = self.project(
                student,
                "Optimisation de requêtes",
                "Analyse des plans d'exécution et création d'index adaptés.",
                assignment_source="teacher_assigned",
                project_assignment=assignment,
                assignment_deadline=assignment.deadline,
                module=module,
                status=status,
                technologies="PostgreSQL, SQL",
                end_date=assignment.deadline.date(),
            )
            DirectStudentAssignment.objects.filter(assignment=assignment, student=student).update(
                status="started" if status == "in_progress" else status
            )
            return project

        solo(s["etu.amine"], "in_progress")
        done = solo(s["etu.salma"], "submitted")
        self.deliverable(done, "Rapport TP", "report")
        solo(s["etu.youssef"], "in_progress")
        self.notify(
            cohort,
            f"Plus que 3 jour(s) pour le rendu du devoir '{assignment.title}' [BDD402] (J-3)",
            kind="assignment_deadline",
            assignment=assignment,
        )

    def seed_ia501(self, module):
        s = self.students
        alami, bennani = self.teachers["prof.alami"], self.teachers["prof.bennani"]
        assignment = self.create_assignment(
            deadline_days=-10,
            selection_days=-30,
            teacher=bennani,
            module=module,
            title="Projet appliqué d'apprentissage automatique",
            description="Résoudre un problème réel avec un modèle supervisé et l'évaluer rigoureusement.",
            assignment_type="choice_based",
            is_team_work=True,
            min_team_size=2,
            max_team_size=3,
            status="published",
        )
        specs = [
            (
                "Détection de maladies des feuilles d'olivier",
                ["etu.hamza", "etu.sara", "etu.othmane"],
                "validated",
                "17.50",
                ["IA", "Data"],
            ),
            (
                "Prévision de la demande électrique régionale",
                ["etu.ghita", "etu.ilyas"],
                "validated",
                "14.00",
                ["Data"],
            ),
            (
                "Classification de réclamations clients en darija",
                ["etu.nour", "etu.yasmine", "etu.badr"],
                "rejected",
                None,
                [],
            ),
        ]
        for order, (title, members, status, score, tags) in enumerate(specs, start=1):
            option = ProjectOption.objects.create(
                assignment=assignment,
                title=title,
                description=f"{title}: collecte, préparation, modélisation et évaluation.",
                order=order,
                current_teams=1,
            )
            owner, *rest = [s[u] for u in members]
            project = self.project(
                owner,
                title,
                option.description,
                members=rest,
                assignment_source="teacher_assigned",
                project_assignment=assignment,
                selected_option=option,
                assignment_deadline=assignment.deadline,
                module=module,
                status=status,
                technologies="Python, scikit-learn, pandas",
                start_date=self.today - timedelta(days=70),
                end_date=assignment.deadline.date(),
                assignment_submitted_at=self.days(-12),
            )
            self.deliverable(project, "Rapport final", "report", versions=2 if order == 1 else 1)
            self.deliverable(project, "Notebook d'expérimentation", "source_code")
            if score:
                self.evaluate(
                    project,
                    bennani if order == 1 else alami,
                    score,
                    "Travail sérieux, démarche expérimentale claire.",
                    [
                        ("Qualité technique", score, ""),
                        ("Livrables & documentation", "15.00", "Rapport bien structuré."),
                        ("Respect des délais", "16.00", ""),
                        ("Présentation & clarté", "14.50", ""),
                    ],
                )
            if status == "rejected":
                ProjectComment.objects.create(
                    project=project,
                    author=bennani.user,
                    content="[FEEDBACK ENSEIGNANT]\nLe jeu de données est trop petit pour conclure.",
                )
            if order == 1:
                self.make_public(
                    project,
                    tags,
                    "Un modèle de vision par ordinateur qui aide les agriculteurs à détecter "
                    "précocement les maladies des oliviers à partir d'une photo.",
                    github="https://github.com/demo/olive-leaf",
                    views=184,
                )
            elif order == 2:
                self.make_public(
                    project,
                    tags,
                    "Prévision à 7 jours de la demande électrique à partir de données météo.",
                    views=57,
                )

    def seed_sem402(self, module):
        s = self.students
        teacher = self.teachers["prof.elidrissi"]
        assignment = self.create_assignment(
            deadline_days=40,
            teacher=teacher,
            module=module,
            title="Station météo connectée",
            description="Concevoir une station météo basse consommation avec remontée des données.",
            assignment_type="direct",
            target_selection="specific_students",
            is_team_work=True,
            min_team_size=2,
            max_team_size=2,
            status="published",
        )
        for username in ["etu.zakaria", "etu.wiam", "etu.ayoub", "etu.chaimae"]:
            DirectStudentAssignment.objects.create(assignment=assignment, student=s[username])
        project = self.project(
            s["etu.zakaria"],
            "Station météo LoRa",
            "Station autonome sur batterie avec transmission LoRa.",
            members=[s["etu.wiam"]],
            assignment_source="teacher_assigned",
            project_assignment=assignment,
            assignment_deadline=assignment.deadline,
            module=module,
            technologies="STM32, LoRa, C",
            end_date=assignment.deadline.date(),
        )
        DirectStudentAssignment.objects.filter(
            assignment=assignment, student__in=[s["etu.zakaria"], s["etu.wiam"]]
        ).update(status="started")
        self.milestones(project, [("Choix des capteurs", -5, True), ("Prototype", 10, False)])

    def seed_log301(self, module, cohort):
        teacher = self.teachers["prof.tazi"]
        assignment = self.create_assignment(
            deadline_days=-5,
            teacher=teacher,
            module=module,
            title="Étude de cas — gestion des stocks",
            description="Proposer une politique de réapprovisionnement pour un entrepôt.",
            assignment_type="direct",
            target_selection="all_students",
            status="published",
        )
        for index, student in enumerate(cohort):
            DirectStudentAssignment.objects.create(assignment=assignment, student=student)
            if index < 3:
                project = self.project(
                    student,
                    "Politique de réapprovisionnement",
                    "Modèle (s, S) simulé sur 12 mois de données.",
                    assignment_source="teacher_assigned",
                    project_assignment=assignment,
                    assignment_deadline=assignment.deadline,
                    module=module,
                    status="validated" if index == 0 else "submitted",
                    technologies="Excel, Python",
                    end_date=assignment.deadline.date(),
                )
                self.deliverable(project, "Rapport d'étude", "report")
                DirectStudentAssignment.objects.filter(
                    assignment=assignment, student=student
                ).update(status="validated" if index == 0 else "submitted")
                if index == 0:
                    self.evaluate(
                        project,
                        teacher,
                        "12.50",
                        "Bonne analyse, simulation perfectible.",
                        [("Analyse", "13.00", ""), ("Simulation", "11.50", "")],
                    )

    def seed_personal_projects(self):
        s = self.students
        specs = [
            (
                "etu.hamza",
                "Stage PFE — plateforme de suivi de flotte",
                "stage_pfe",
                "Transports Atlas, Casablanca",
                "validated",
                ["Web", "Data"],
                "Plateforme de suivi temps réel d'une flotte de 120 véhicules.",
            ),
            (
                "etu.sara",
                "Application mobile de don de sang",
                "stage_ingenieur",
                "Centre régional de transfusion, Kénitra",
                "validated",
                ["Mobile"],
                "Mise en relation des donneurs avec les centres selon les besoins en temps réel.",
            ),
            (
                "etu.zakaria",
                "Contrôle d'irrigation par capteurs d'humidité",
                "stage_initiation",
                "Coopérative agricole Gharb",
                "validated",
                ["IoT", "Industrie"],
                "Réduction de 30 % de la consommation d'eau sur une parcelle pilote.",
            ),
            (
                "etu.amine",
                "Portfolio et blog technique",
                "module",
                "",
                "in_progress",
                [],
                "",
            ),
            (
                "etu.salma",
                "Stage d'initiation — audit de sécurité web",
                "stage_initiation",
                "Agence digitale, Rabat",
                "validated",
                ["Web"],
                "Audit OWASP d'un site e-commerce et plan de remédiation.",
            ),
        ]
        for username, title, kind, company, status, tags, public_text in specs:
            project = self.project(
                s[username],
                title,
                public_text or "Projet personnel en cours.",
                project_type=kind,
                module_or_company=company,
                status=status,
                technologies="Django, React" if "Web" in tags else "",
                end_date=self.today - timedelta(days=20) if status == "validated" else None,
            )
            if status == "validated":
                self.deliverable(project, "Rapport de stage", "report")
            if tags:
                self.make_public(
                    project,
                    tags,
                    public_text,
                    demo="https://demo.example.org" if username == "etu.hamza" else "",
                    views=self.rng.randint(10, 120),
                )

    def seed_social(self):
        users = [p.user for p in self.students.values()] + [t.user for t in self.teachers.values()]
        public = list(Project.objects.filter(is_public=True))
        for project in public:
            likers = self.rng.sample(users, self.rng.randint(1, 9))
            for user in likers:
                ProjectLike.objects.create(project=project, user=user)
            project.like_count = len(likers)
            project.save(update_fields=["like_count"])
        comments = [
            "Très beau travail, la démo est convaincante.",
            "Est-ce que le code sera open source ?",
            "Bravo à toute l'équipe !",
        ]
        for project, text in zip(public, comments, strict=False):
            PublicProjectComment.objects.create(
                project=project, author=self.rng.choice(users), content=text
            )

        # A reported project (3 reports → flagged) and a hidden one
        flagged = public[-1]
        reasons = ["spam", "false_info", "other"]
        for user, reason in zip(users[:3], reasons, strict=True):
            ProjectReport.objects.create(
                project=flagged,
                reporter=user,
                reason=reason,
                description="Le contenu ne semble pas correspondre au projet décrit.",
            )
        flagged.report_count = 3
        flagged.is_reported = True
        flagged.save(update_fields=["report_count", "is_reported"])

    def seed_registrations(self):
        pending = [
            ("etu.new1", "Achraf", "Boukili", "student", "E2023101", 3, "Génie Informatique"),
            ("etu.new2", "Oumaima", "Lazrak", "student", "E2023102", 3, "Génie Électrique"),
            ("prof.new", "Hicham", "Rachidi", "teacher", None, None, "Génie Informatique"),
        ]
        for username, first, last, role, student_id, year, department in pending:
            PendingRegistration.objects.create(
                username=username,
                first_name=first,
                last_name=last,
                email=f"{username.replace('.', '_')}@{EMAIL_DOMAIN}",
                password=self.password_hash,
                role=role,
                student_id=student_id,
                year_of_study=year,
                department=department,
            )
