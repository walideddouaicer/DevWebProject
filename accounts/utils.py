# accounts/utils.py
from ensa_project_manager.emails import absolute_url, send_templated_email


def send_registration_confirmation_email(registration):
    """Acknowledge a signup request (it still needs admin approval)."""
    return send_templated_email(
        "Demande d'inscription reçue — ENSA Project Manager",
        "registration_received",
        {"registration": registration},
        [registration.email],
    )


def send_approval_email(registration):
    """Tell the user their account is active, with a working login link."""
    return send_templated_email(
        "Votre compte est activé — ENSA Project Manager",
        "registration_approved",
        {"registration": registration, "login_url": absolute_url("login")},
        [registration.email],
    )
