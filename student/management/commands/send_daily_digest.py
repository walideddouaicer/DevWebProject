# Daily email digest (ROADMAP #14).
#
# Run once a day by the scheduler container (run_scheduler), or by hand:
#   python manage.py send_daily_digest [--dry-run]
#
# Students who enabled the digest preference receive ONE summary email of
# their unread notifications from the last 24 hours, instead of an email
# per event (the immediate-email paths skip digest users).

from django.core.management.base import BaseCommand
from django.utils import timezone

from ensa_project_manager.emails import absolute_url, send_templated_email
from student.models import Notification, UserPreferences

MAX_ITEMS = 30


class Command(BaseCommand):
    help = "Envoie le résumé quotidien des notifications aux étudiants qui l'ont activé."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Fenêtre des notifications à résumer (défaut: 24h).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les digests qui seraient envoyés sans rien envoyer.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        since = timezone.now() - timezone.timedelta(hours=options["hours"])
        sent = 0

        digest_prefs = UserPreferences.objects.filter(
            email_digest=True,
            email_notifications=True,
        ).select_related("user__studentprofile")

        for prefs in digest_prefs:
            user = prefs.user
            student = getattr(user, "studentprofile", None)
            if not user.email or not user.is_active or student is None:
                continue

            unread = Notification.objects.filter(
                recipient=student, is_read=False, created_at__gte=since
            ).order_by("created_at")
            total = unread.count()
            if not total:
                continue

            if dry_run:
                self.stdout.write(f"[dry-run] {user.username}: {total} notification(s)")
                sent += 1
                continue

            if send_templated_email(
                f"Votre résumé quotidien — {total} notification{'s' if total > 1 else ''}",
                "digest",
                {
                    "recipient_name": user.first_name or user.username,
                    "notifications": unread[:MAX_ITEMS],
                    "total": total,
                    "extra": max(0, total - MAX_ITEMS),
                    "notifications_url": absolute_url("student:notifications"),
                    "settings_url": absolute_url("student:profile_settings") + "?tab=notifications",
                },
                [user.email],
            ):
                sent += 1

        verb = "seraient envoyés" if dry_run else "envoyés"
        self.stdout.write(self.style.SUCCESS(f"{sent} digest(s) {verb}."))
