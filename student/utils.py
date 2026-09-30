# sending emails
import logging

from django.core.cache import cache
from django.utils import timezone


def group_deliverables(queryset):
    """Latest deliverable per name, each carrying `.history` (older versions).

    Returns a list of ProjectDeliverable instances (newest version of each
    name, in recent-first order) with an extra `history` attribute holding
    the older versions, newest first.
    """
    groups = {}
    for deliverable in queryset.order_by("name", "-version", "-upload_date"):
        if deliverable.name not in groups:
            deliverable.history = []
            groups[deliverable.name] = deliverable
        else:
            groups[deliverable.name].history.append(deliverable)
    # Show most recently updated deliverables first
    return sorted(groups.values(), key=lambda d: d.upload_date, reverse=True)


def clear_student_context_cache(student):
    """Invalidate the cached navbar badge counts for a student.

    Must be called whenever notifications/invitations change so the
    badges update immediately instead of waiting for the cache TTL.
    """
    hour = timezone.now().hour
    cache.delete_many(
        [
            f"student_context_{student.id}_{hour}",
            f"student_nav_{student.id}_{hour}",
        ]
    )


# Get a logger for this module
logger = logging.getLogger(__name__)


def send_invitation_email(invitation):
    """Email the invitation recipient, respecting their notification preferences."""
    from ensa_project_manager.emails import absolute_url, send_templated_email

    recipient_user = invitation.recipient.user
    prefs = getattr(recipient_user, "preferences", None)
    if prefs is not None and (
        not prefs.email_notifications
        or not prefs.collaboration_notifications
        or prefs.email_digest  # digest users get a daily summary instead
    ):
        return False
    sender = invitation.sender.user
    return send_templated_email(
        f"Invitation à rejoindre le projet « {invitation.project.title} »",
        "invitation",
        {
            "recipient_name": recipient_user.first_name or recipient_user.username,
            "sender_name": sender.get_full_name() or sender.username,
            "project": invitation.project,
            "invitations_url": absolute_url("student:invitations_list"),
        },
        [recipient_user.email],
    )
