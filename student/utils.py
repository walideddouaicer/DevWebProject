# sending emails
from django.core.mail import send_mail
from django.conf import settings
import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

def send_invitation_email(invitation):
    """Send notification email when a collaboration invitation is sent"""
    try:
        recipient_email = invitation.recipient.user.email
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