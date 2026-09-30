from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import (
    AccountSettingsForm,
    StudentProfileForm,
)
from ..models import (
    StudentProfile,
)


@login_required
def profile_settings(request):
    """Main profile and settings page with tabs"""
    student = get_object_or_404(StudentProfile, user=request.user)

    # Get current tab (default to profile)
    active_tab = request.GET.get("tab", "profile")

    from ..models import UserPreferences

    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    context = {
        "student": student,
        "active_tab": active_tab,
        "profile_completion": student.get_profile_completion_percentage(),
        "preferences": preferences,
    }

    return render(request, "student/profile_settings.html", context)


@login_required
def profile_edit(request):
    """Edit student profile information"""
    student = get_object_or_404(StudentProfile, user=request.user)

    if request.method == "POST":
        form = StudentProfileForm(request.POST, request.FILES, instance=student, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès!")
            return redirect("student:profile_settings")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = StudentProfileForm(instance=student, user=request.user)

    context = {
        "student": student,
        "form": form,
        "profile_completion": student.get_profile_completion_percentage(),
    }

    return render(request, "student/profile_edit.html", context)


@login_required
def profile_view(request):
    """View own profile (read-only)"""
    student = get_object_or_404(StudentProfile, user=request.user)

    context = {
        "student": student,
        "profile_completion": student.get_profile_completion_percentage(),
        "is_own_profile": True,
    }

    return render(request, "student/profile_view.html", context)


@login_required
def account_settings(request):
    """Account settings and preferences"""
    get_object_or_404(StudentProfile, user=request.user)

    # Check if password was just changed
    password_changed = request.GET.get("changed") == "true"

    from ..models import UserPreferences

    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = AccountSettingsForm(request.POST)
        if form.is_valid():
            # Handle settings changes
            if form.cleaned_data.get("change_password"):
                # Redirect to password change
                return redirect("student:password_change")

            # Persist notification preferences
            preferences.email_notifications = form.cleaned_data.get("email_notifications", False)
            preferences.project_notifications = form.cleaned_data.get(
                "project_notifications", False
            )
            preferences.collaboration_notifications = form.cleaned_data.get(
                "collaboration_notifications", False
            )
            preferences.email_digest = request.POST.get("email_digest") == "on"
            preferences.save()

            messages.success(request, "Préférences de notification mises à jour!")
            return redirect("/student/settings/?tab=notifications")

    # The account settings UI lives in the tabbed settings page
    # (there is no standalone account_settings template).
    if password_changed:
        return redirect("/student/settings/?tab=account&changed=true")
    return redirect("/student/settings/?tab=account")


@login_required
def delete_profile_picture(request):
    """Delete profile picture (AJAX endpoint)"""
    if request.method == "POST":
        student = get_object_or_404(StudentProfile, user=request.user)

        if student.profile_picture:
            # Delete the file
            student.profile_picture.delete()
            messages.success(request, "Photo de profil supprimée avec succès.")
        else:
            messages.warning(request, "Aucune photo de profil à supprimer.")

        return redirect("student:profile_edit")

    return redirect("student:profile_settings")
