"""Send a test email with the current settings (PLAN P4.8).

python manage.py check_email you@example.com
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envoie un e-mail de test pour vérifier la configuration SMTP."

    def add_arguments(self, parser):
        parser.add_argument("recipient")

    def handle(self, *args, **options):
        self.stdout.write(
            f"Backend: {settings.EMAIL_BACKEND} host={settings.EMAIL_HOST}:{settings.EMAIL_PORT} "
            f"from={settings.DEFAULT_FROM_EMAIL}"
        )
        try:
            send_mail(
                "Test d'envoi — ENSA Project Manager",
                "Si vous lisez ce message, l'envoi d'e-mails fonctionne.",
                settings.DEFAULT_FROM_EMAIL,
                [options["recipient"]],
                fail_silently=False,
            )
        except Exception as error:
            raise CommandError(f"Échec de l'envoi : {error}")
        self.stdout.write(self.style.SUCCESS(f"E-mail envoyé à {options['recipient']}."))
