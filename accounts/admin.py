import logging

from django.contrib import admin, messages

# accounts/admin.py
from django.db import IntegrityError

from .models import PendingRegistration

logger = logging.getLogger(__name__)


@admin.action(description="Approuver les demandes sélectionnées")
def approve_registrations(modeladmin, request, queryset):
    approved = 0
    for registration in queryset.filter(is_approved=False):
        try:
            registration.approve(by=request.user)
            approved += 1
        except IntegrityError:
            messages.error(request, f"{registration.username} : identifiant déjà utilisé.")
    messages.success(request, f"{approved} demande(s) approuvée(s).")


@admin.action(description="Reject selected registrations")
def reject_registrations(modeladmin, request, queryset):
    """Reject pending registrations"""
    rejected_count = queryset.filter(is_approved=False).delete()[0]
    messages.success(request, f"Rejected {rejected_count} registrations.")


class PendingRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "role",
        "is_approved",
        "created_at",
    )
    list_filter = ("role", "is_approved", "created_at", "department")
    search_fields = ("username", "first_name", "last_name", "email", "student_id", "teacher_id")
    readonly_fields = ("password", "created_at", "approved_at")
    actions = [approve_registrations, reject_registrations]

    fieldsets = (
        (
            "User Information",
            {"fields": ("username", "first_name", "last_name", "email", "password")},
        ),
        (
            "Role & Details",
            {"fields": ("role", "student_id", "teacher_id", "department", "year_of_study")},
        ),
        (
            "Approval Status",
            {"fields": ("is_approved", "approved_by", "created_at", "approved_at")},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("approved_by")


admin.site.register(PendingRegistration, PendingRegistrationAdmin)
