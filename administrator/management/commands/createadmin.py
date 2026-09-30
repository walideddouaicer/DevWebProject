"""Create (or promote) the application administrator (PLAN P4.8).

    python manage.py createadmin --username admin --email admin@ensa.ma
    python manage.py createadmin                      # reads ADMIN_USERNAME / ADMIN_EMAIL

A strong password is generated and printed ONCE unless --password or ADMIN_PASSWORD is
given. The user gets an AdminProfile (the app's admin role) and Django-admin access.
"""

import os
import secrets

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administrator.models import AdminProfile


class Command(BaseCommand):
    help = "Crée le compte administrateur de l'application (mot de passe affiché une fois)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("ADMIN_USERNAME"))
        parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
        parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args, **options):
        username, email = options["username"], options["email"]
        if not username or not email:
            raise CommandError(
                "--username and --email (or ADMIN_USERNAME/ADMIN_EMAIL) are required."
            )
        password = options["password"] or secrets.token_urlsafe(16)
        generated = not options["password"]

        with transaction.atomic():
            user, created = User.objects.get_or_create(username=username, defaults={"email": email})
            if created or options["password"]:
                try:
                    validate_password(password, user)
                except ValidationError as error:
                    raise CommandError(" ".join(error.messages))
                user.set_password(password)
            user.email = email
            user.first_name = options["first_name"] or user.first_name
            user.last_name = options["last_name"] or user.last_name
            user.is_staff = user.is_superuser = user.is_active = True
            user.save()
            AdminProfile.objects.get_or_create(user=user)

        if created:
            self.stdout.write(self.style.SUCCESS(f"Administrateur « {username} » créé."))
            if generated:
                self.stdout.write(f"Mot de passe (affiché une seule fois) : {password}")
        else:
            self.stdout.write(self.style.SUCCESS(f"« {username} » est administrateur."))
