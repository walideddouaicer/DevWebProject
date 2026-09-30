"""Deployment checks (`manage.py check --deploy`), PLAN P4.1."""

from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def production_configuration(app_configs, **kwargs):
    warnings = []
    if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend") and not settings.EMAIL_HOST:
        warnings.append(
            Warning(
                "EMAIL_HOST is empty: password resets and notifications will not be delivered.",
                id="ensa.W001",
            )
        )
    if not settings.SITE_URL.startswith("https://"):
        warnings.append(Warning("SITE_URL should be the public https:// address.", id="ensa.W002"))
    if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
        warnings.append(
            Warning("SQLite is not suitable for production; set DATABASE_URL.", id="ensa.W003")
        )
    return warnings
