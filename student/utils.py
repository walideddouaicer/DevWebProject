# sending emails
import logging


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


# Get a logger for this module
logger = logging.getLogger(__name__)


def send_invitation_email(invitation):
    """Email the invitation recipient, respecting their notification preferences."""
    from ensa_project_manager.emails import absolute_url, send_templated_email, wants_email

    recipient_user = invitation.recipient.user
    if not wants_email(recipient_user, "collaboration_notifications"):
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
