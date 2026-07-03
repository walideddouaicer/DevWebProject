# sending emails
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import logging


def group_deliverables(queryset):
    """Latest deliverable per name, each carrying `.history` (older versions).

    Returns a list of ProjectDeliverable instances (newest version of each
    name, in recent-first order) with an extra `history` attribute holding
    the older versions, newest first.
    """
    groups = {}
    for deliverable in queryset.order_by('name', '-version', '-upload_date'):
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
    cache.delete_many([
        f"student_context_{student.id}_{hour}",
        f"student_nav_{student.id}_{hour}",
    ])

# Get a logger for this module
logger = logging.getLogger(__name__)

def send_invitation_email(invitation):
    """Send notification email when a collaboration invitation is sent"""
    try:
        # Respect the recipient's notification preferences
        recipient_user = invitation.recipient.user
        if hasattr(recipient_user, 'preferences'):
            prefs = recipient_user.preferences
            if not prefs.email_notifications or not prefs.collaboration_notifications:
                return False
            if prefs.email_digest:
                # Digest users get a daily summary instead of per-event emails
                return False

        recipient_email = recipient_user.email
        sender_name = invitation.sender.user.get_full_name() or invitation.sender.user.username
        project_title = invitation.project.title
        
        subject = f"Invitation à collaborer sur le projet: {project_title}"
        message = f"""
        Bonjour,
        
        {sender_name} vous invite à collaborer sur le projet "{project_title}".
        
        Pour répondre à cette invitation, connectez-vous à votre compte ENSA Project Manager.
        
        Cordialement,
        L'équipe ENSA Project Manager
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
        )
        
        return True
    except Exception as e:
        # Log but don't raise the exception
        logger.error(f"Email sending failed: {e}")
        print(f"Email sending failed: {e}")
        return False