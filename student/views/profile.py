from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.permissions import student_required

from ..forms import NotificationPreferencesForm, StudentProfileForm
from ..models import UserPreferences

SETTINGS_TABS = ("profile", "notifications", "appearance", "account")


def _settings_url(tab):
    return f"{reverse('student:profile_settings')}?tab={tab}"


@student_required
def profile_settings(request):
    """Settings page with tabs: profil, notifications, apparence, compte."""
    student = request.student
    active_tab = request.GET.get("tab", "profile")
    if active_tab not in SETTINGS_TABS:
        active_tab = "profile"
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    context = {
        "student": student,
        "active_tab": active_tab,
        "profile_completion": student.get_profile_completion_percentage(),
        "preferences": preferences,
        "notification_form": NotificationPreferencesForm(instance=preferences),
    }
    return render(request, "student/profile_settings.html", context)


@student_required
def profile_edit(request):
    """Edit profile information (name, contact, links, photo)."""
    student = request.student
    if request.method == "POST":
        form = StudentProfileForm(request.POST, request.FILES, instance=student, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect("student:profile_view")
        messages.error(request, "Veuillez corriger les erreurs indiquées.")
    else:
        form = StudentProfileForm(instance=student, user=request.user)
    context = {
        "student": student,
        "form": form,
        "profile_completion": student.get_profile_completion_percentage(),
    }
    return render(request, "student/profile_edit.html", context)


@student_required
def profile_view(request):
    """Own profile (read-only)."""
    student = request.student
    context = {
        "student": student,
        "profile_completion": student.get_profile_completion_percentage(),
        "is_own_profile": True,
    }
    return render(request, "student/profile_view.html", context)


@student_required
def account_settings(request):
    """Save notification preferences (POST); GET goes to the settings page."""
    if request.method != "POST":
        return redirect(_settings_url("account"))
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    form = NotificationPreferencesForm(request.POST, instance=preferences)
    if form.is_valid():
        form.save()
        messages.success(request, "Préférences de notification enregistrées.")
    else:
        messages.error(request, "Préférences invalides.")
    return redirect(_settings_url("notifications"))


@student_required
@require_POST
def delete_profile_picture(request):
    student = request.student
    if student.profile_picture:
        student.profile_picture.delete()
        messages.success(request, "Photo de profil supprimée.")
    return redirect("student:profile_edit")
