"""Development-only previews of every transactional email (PLAN P6.12).

/_emails/                 index
/_emails/<name>/          HTML version
/_emails/<name>/?txt=1    plain-text version

The sample contexts double as fixtures for tests/test_emails.py, which renders all of them.
"""

from datetime import timedelta
from types import SimpleNamespace as NS

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .emails import render_email


def _url(path):
    return f"{settings.SITE_URL}{path}"


def samples():
    """{name: context} with realistic French content."""
    now = timezone.now()
    registration = NS(
        first_name="Salma",
        username="salma.chraibi",
        email="salma@example.com",
        get_role_display="Étudiant",
    )
    module = NS(code="WEB401", name="Développement web avancé")
    project = NS(
        title="Plateforme de réservation pour un riad",
        project_assignment=NS(title="Projet de fin de module — application web"),
    )
    settings_url = _url("/student/settings/?tab=notifications")
    notifications = [
        NS(message=message, created_at=now - timedelta(hours=hours))
        for message, hours in [
            ("Karim Alami demande des révisions sur le projet « Station météo LoRa ».", 20),
            ("Plus que 3 jour(s) pour le rendu du devoir 'Rapport final' [SEM402] (J-3)", 9),
            ("[WEB401] Soutenances — Les soutenances auront lieu le 14 octobre.", 2),
        ]
    ]
    return {
        "registration_received": {"registration": registration},
        "registration_approved": {"registration": registration, "login_url": _url("/login/")},
        "invitation": {
            "recipient_name": "Amine",
            "sender_name": "Youssef Ouazzani",
            "project": project,
            "invitations_url": _url("/student/invitations/"),
        },
        "announcement": {
            "user": NS(first_name="Amine", username="amine"),
            "teacher_name": "Karim Alami",
            "module": module,
            "title": "Soutenances",
            "content": "Les soutenances auront lieu le 14 octobre en salle B12.\n"
            "Prévoyez 10 minutes de présentation et 5 minutes de questions.",
            "modules_url": _url("/student/modules/"),
        },
        "password_reset": {
            "user": NS(first_name="Salma", get_username="salma.chraibi"),
            "protocol": "https",
            "domain": settings.SITE_URL.split("://", 1)[-1],
            "uid": "MQ",
            "token": "cdx7ab-0123456789abcdef",
        },
        "project_update": {
            "recipient_name": "Amine",
            "project": project,
            "heading": "Révisions demandées",
            "message": "Karim Alami demande des révisions sur le projet « Plateforme de "
            "réservation pour un riad ». Consultez ses commentaires puis soumettez à nouveau.",
            "details": "La page de paiement ne gère pas les erreurs de carte.\n"
            "Ajoutez des tests pour le calcul des nuitées.",
            "project_url": _url("/student/projects/1/"),
            "settings_url": settings_url,
        },
        "deadline_reminder": {
            "recipient_name": "Amine",
            "assignment": NS(title="Rapport final", module=module),
            "lead": "Plus que 3 jours pour le rendu du devoir « Rapport final »",
            "deadline": now + timedelta(days=3),
            "assignment_url": _url("/student/assignments/1/"),
            "settings_url": settings_url,
        },
        "digest": {
            "recipient_name": "Amine",
            "notifications": notifications,
            "total": 5,
            "extra": 2,
            "notifications_url": _url("/student/notifications/"),
            "settings_url": settings_url,
        },
    }


def email_index(request):
    return render(request, "emails/_preview_index.html", {"names": sorted(samples())})


def email_preview(request, name):
    context = samples().get(name)
    if context is None:
        raise Http404(name)
    text, html = render_email(name, context)
    if request.GET.get("txt") or html is None:
        return HttpResponse(text, content_type="text/plain; charset=utf-8")
    return HttpResponse(html)
