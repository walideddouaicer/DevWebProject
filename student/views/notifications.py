from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, OuterRef, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import (
    CollaborationInvitation,
    Notification,
    StudentProfile,
)
from ..utils import clear_student_context_cache


@login_required
def notifications(request):
    """Display all notifications for the current user"""
    student = get_object_or_404(StudentProfile, user=request.user)

    # Fetch notifications and prefetch related invitations
    # Annotate each notification with the status of the relevant invitation if it exists
    notifications = Notification.objects.filter(recipient=student)

    notifications = notifications.annotate(
        invitation_status=Case(
            When(
                notification_type="invitation",
                then=CollaborationInvitation.objects.filter(
                    project=OuterRef("project"), recipient=OuterRef("recipient")
                ).values("status")[:1],  # Get the status of the first matching invitation
            ),
            default=None,  # Default for non-invitation notifications
        )
    ).order_by("-created_at")

    context = {
        "notifications": notifications,
    }
    return render(request, "student/notifications.html", context)


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    student = get_object_or_404(StudentProfile, user=request.user)
    notification = get_object_or_404(Notification, id=notification_id, recipient=student)
    notification.is_read = True
    notification.save()
    clear_student_context_cache(student)
    return redirect("student:notifications")


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    student = get_object_or_404(StudentProfile, user=request.user)
    Notification.objects.filter(recipient=student, is_read=False).update(is_read=True)
    clear_student_context_cache(student)
    messages.success(request, "Toutes les notifications ont été marquées comme lues.")
    return redirect("student:notifications")
