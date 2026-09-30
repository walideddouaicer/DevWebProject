"""UI endpoints: theme preference (P5.7) and the development-only styleguide (P5.5)."""

from datetime import timedelta

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

THEMES = {"light", "dark", "auto"}


@login_required
@require_POST
def set_theme(request):
    """Save the light/dark/auto preference for any signed-in user (fetch from app.js)."""
    from student.models import UserPreferences

    theme = request.POST.get("theme")
    if theme not in THEMES:
        return HttpResponseBadRequest("theme must be light, dark or auto")
    UserPreferences.objects.update_or_create(
        user=request.user, defaults={"theme_preference": theme}
    )
    return HttpResponse(status=204)


class DemoForm(forms.Form):
    title = forms.CharField(label="Titre du projet", help_text="Un titre court et précis.")
    description = forms.CharField(label="Description", widget=forms.Textarea, required=False)
    module = forms.ChoiceField(
        label="Module", choices=[("", "Choisir…"), ("web", "WEB401 — Développement web")]
    )
    email = forms.EmailField(label="Adresse e-mail")
    public = forms.BooleanField(label="Rendre les livrables publics", required=False)


class Person:
    def __init__(self, first, last):
        self.first, self.last = first, last

    def get_full_name(self):
        return f"{self.first} {self.last}"

    def get_username(self):
        return self.first.lower()


def styleguide(request):
    now = timezone.now()
    bound = DemoForm(data={"title": "", "email": "pas-un-email", "module": "web"})
    bound.is_valid()
    context = {
        "form": DemoForm(),
        "bound": bound,
        "people": [
            Person(*n.split())
            for n in [
                "Amine Berrada",
                "Salma Chraibi",
                "Youssef Ouazzani",
                "Imane Lahlou",
                "Hajar Benjelloun",
                "Karim Alami",
            ]
        ],
        "statuses": [
            "in_progress",
            "submitted",
            "revision_requested",
            "validated",
            "rejected",
            "draft",
            "published",
            "pending",
        ],
        "deadlines": [
            now - timedelta(days=2),
            now + timedelta(hours=3),
            now + timedelta(days=1),
            now + timedelta(days=3),
            now + timedelta(days=12),
        ],
        "days": range(1, 36),
    }
    return render(request, "ui/styleguide.html", context)


@login_required
def styleguide_shell(request):
    """Preview of the authenticated shell with a realistic page (development only)."""
    return render(request, "ui/styleguide_shell.html", {"now": timezone.now()})
