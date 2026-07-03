# Deadline reminder job (ROADMAP item #1).
#
# Run daily (Windows Task Scheduler / cron):
#   venv\Scripts\python.exe manage.py send_deadline_reminders
#
# For every published assignment, students who still have work to do receive an
# in-app Notification at J-7, J-3, J-1 and J-0 (deadline day) — both for the
# final deadline and, on choice-based assignments, the selection deadline.
# Emails are sent only if the student's UserPreferences allow it.
# A (J-x) marker in the message guarantees each threshold fires only once.

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from student.models import StudentProfile, Project, Notification, UserPreferences
from teacher.models import ProjectAssignment, DirectStudentAssignment

THRESHOLDS = [7, 3, 1, 0]  # days before the deadline


class Command(BaseCommand):
    help = "Envoie les rappels de dates limites (devoirs) aux étudiants concernés."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche les rappels qui seraient envoyés sans rien créer."
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        now = timezone.now()
        created_count = 0

        assignments = ProjectAssignment.objects.filter(
            status__in=['published', 'in_progress']
        ).select_related('module')

        for assignment in assignments:
            # --- Final deadline reminders ---
            if assignment.deadline and assignment.deadline > now:
                days_left = (assignment.deadline - now).days
                if days_left in THRESHOLDS:
                    for student in self.students_needing_submission(assignment):
                        created_count += self.remind(
                            student, assignment, 'final', days_left
                        )

            # --- Selection deadline reminders (choice-based only) ---
            if (assignment.assignment_type == 'choice_based'
                    and assignment.selection_deadline
                    and assignment.selection_deadline > now):
                days_left = (assignment.selection_deadline - now).days
                if days_left in THRESHOLDS:
                    for student in self.students_without_project(assignment):
                        created_count += self.remind(
                            student, assignment, 'selection', days_left
                        )

        verb = "seraient envoyés" if self.dry_run else "envoyés"
        self.stdout.write(self.style.SUCCESS(f"{created_count} rappel(s) {verb}."))

    # ------------------------------------------------------------------
    # Target students

    def students_needing_submission(self, assignment):
        """Students expected to submit who haven't submitted yet."""
        targets = self.target_students(assignment)

        # Students already covered by a submitted/validated project (as owner
        # or collaborator) don't need a reminder.
        done_projects = Project.objects.filter(
            project_assignment=assignment,
            status__in=['submitted', 'validated']
        )
        done_ids = set(done_projects.values_list('student_id', flat=True))
        done_ids.update(done_projects.values_list('collaborators__id', flat=True))
        done_ids.discard(None)

        return [s for s in targets if s.id not in done_ids]

    def students_without_project(self, assignment):
        """Students who haven't created/joined any project for the assignment."""
        targets = self.target_students(assignment)

        projects = Project.objects.filter(project_assignment=assignment)
        involved_ids = set(projects.values_list('student_id', flat=True))
        involved_ids.update(projects.values_list('collaborators__id', flat=True))
        involved_ids.discard(None)

        return [s for s in targets if s.id not in involved_ids]

    def target_students(self, assignment):
        if assignment.assignment_type == 'direct':
            return list(StudentProfile.objects.filter(
                direct_assignments__assignment=assignment
            ).select_related('user'))
        return list(StudentProfile.objects.filter(
            module_enrollments__module=assignment.module,
            module_enrollments__is_active=True
        ).select_related('user'))

    # ------------------------------------------------------------------
    # Sending

    def remind(self, student, assignment, deadline_type, days_left):
        """Create the notification (and email) for one student. Returns 1 if sent."""
        marker = f"(J-{days_left})"
        if deadline_type == 'selection':
            what = f"la sélection de projet pour '{assignment.title}'"
            deadline = assignment.selection_deadline
        else:
            what = f"le rendu du devoir '{assignment.title}'"
            deadline = assignment.deadline

        if days_left == 0:
            lead = f"Dernier jour pour {what}"
        else:
            lead = f"Plus que {days_left} jour(s) pour {what}"

        message = (
            f"{lead} — date limite: {timezone.localtime(deadline).strftime('%d/%m/%Y %H:%M')} "
            f"[{assignment.module.code}] {marker}"
        )

        # Already reminded for this threshold?
        if Notification.objects.filter(
            recipient=student,
            project_assignment=assignment,
            notification_type='assignment_deadline',
            message__endswith=marker,
        ).exists():
            return 0

        if self.dry_run:
            self.stdout.write(f"  [dry-run] {student.user.username}: {message}")
            return 1

        Notification.objects.create(
            recipient=student,
            project_assignment=assignment,
            notification_type='assignment_deadline',
            message=message,
        )
        self.send_email(student, assignment, message)
        return 1

    def send_email(self, student, assignment, message):
        """Email the reminder if the student's preferences allow it."""
        user = student.user
        if not user.email:
            return
        prefs = UserPreferences.objects.filter(user=user).first()
        if prefs and not (prefs.email_notifications and prefs.assignment_reminders):
            return
        try:
            send_mail(
                subject=f"Rappel de date limite — {assignment.title}",
                message=(
                    f"Bonjour {user.first_name or user.username},\n\n"
                    f"{message}\n\n"
                    "Connectez-vous à ENSA Project Manager pour soumettre votre travail.\n\n"
                    "Cordialement,\nL'équipe ENSA Project Manager"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            # Never let email problems break the reminder job
            pass
