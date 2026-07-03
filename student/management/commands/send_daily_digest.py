# Daily email digest (ROADMAP #14).
#
# Run once a day (Windows Task Scheduler / cron):
#   venv\Scripts\python.exe manage.py send_daily_digest
#
# Students who enabled the digest preference receive ONE summary email of
# their unread notifications from the last 24 hours, instead of an email
# per event (the immediate-email paths skip digest users).

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from student.models import Notification, UserPreferences


class Command(BaseCommand):
    help = "Envoie le résumé quotidien des notifications aux étudiants qui l'ont activé."

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours', type=int, default=24,
            help="Fenêtre des notifications à résumer (défaut: 24h)."
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche les digests qui seraient envoyés sans rien envoyer."
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        since = timezone.now() - timezone.timedelta(hours=options['hours'])
        sent = 0

        digest_prefs = UserPreferences.objects.filter(
            email_digest=True,
            email_notifications=True,
        ).select_related('user')

        for prefs in digest_prefs:
            user = prefs.user
            if not user.email:
                continue

            student = getattr(user, 'studentprofile', None)
            if student is None:
                continue

            notifications = Notification.objects.filter(
                recipient=student,
                is_read=False,
                created_at__gte=since,
            ).order_by('created_at')

            if not notifications.exists():
                continue

            lines = [f"• {n.message}" for n in notifications[:30]]
            extra = notifications.count() - 30
            if extra > 0:
                lines.append(f"... et {extra} autre(s) notification(s).")

            body = (
                f"Bonjour {user.first_name or user.username},\n\n"
                f"Voici votre résumé quotidien ENSA Project Manager "
                f"({notifications.count()} notification(s) non lue(s)):\n\n"
                + "\n".join(lines)
                + "\n\nConnectez-vous pour voir les détails: /student/notifications/\n\n"
                "Cordialement,\nENSA Project Manager\n\n"
                "Vous recevez ce résumé car le mode digest est activé dans vos paramètres."
            )

            if dry_run:
                self.stdout.write(f"[dry-run] {user.username}: {notifications.count()} notification(s)")
                sent += 1
                continue

            try:
                send_mail(
                    subject=f"Votre résumé quotidien — {notifications.count()} notification(s)",
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                sent += 1
            except Exception:
                pass

        verb = "seraient envoyés" if dry_run else "envoyés"
        self.stdout.write(self.style.SUCCESS(f"{sent} digest(s) {verb}."))
