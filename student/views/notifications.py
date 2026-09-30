from django.contrib import messages
from django.db.models import Case, OuterRef, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import student_required
from ensa_project_manager.pagination import paginate

from ..models import (
    CollaborationInvitation,
    Notification,
)


@student_required
def notifications(request):
    """Display all notifications for the current user"""
    student = request.student

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

    page_obj = paginate(request, notifications)
    context = {
        "notifications": page_obj,
        "today": timezone.localdate(),
        "page_obj": page_obj,
    }
    return render(request, "student/notifications.html", context)


@student_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    student = request.student
    notification = get_object_or_404(Notification, id=notification_id, recipient=student)
    notification.is_read = True
    notification.save()
    return redirect("student:notifications")


@student_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    student = request.student
    Notification.objects.filter(recipient=student, is_read=False).update(is_read=True)
    messages.success(request, "Toutes les notifications ont été marquées comme lues.")
    return redirect("student:notifications")
