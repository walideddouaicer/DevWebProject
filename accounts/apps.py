from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Project-wide deployment checks live in ensa_project_manager/checks.py
        from ensa_project_manager import checks  # noqa: F401
