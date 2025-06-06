# accounts/utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)

def send_registration_confirmation_email(registration):
    """Send confirmation email when registration is submitted"""
    try:
        subject = "Demande d'inscription reçue - ENSA Project Manager"
        message = f"""
        Bonjour {registration.first_name},
        
        Votre demande d'inscription en tant que {registration.get_role_display()} a été reçue.
        
        Détails de votre demande:
        - Nom d'utilisateur: {registration.username}
        - Email: {registration.email}
        - Rôle: {registration.get_role_display()}
        
        Un administrateur examinera votre demande sous peu. Vous recevrez un email de confirmation une fois votre compte approuvé.
        
        Cordialement,
        L'équipe ENSA Project Manager
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [registration.email],
            fail_silently=False,
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email to {registration.email}: {e}")
        return False

def send_approval_email(registration):
    """Send email when registration is approved"""
    try:
        subject = "Compte approuvé - ENSA Project Manager"
        message = f"""
        Bonjour {registration.first_name},
        
        Excellente nouvelle! Votre compte ENSA Project Manager a été approuvé.
        
        Vous pouvez maintenant vous connecter avec:
        - Nom d'utilisateur: {registration.username}
        - Mot de passe: Celui que vous avez choisi lors de l'inscription
        
        Connectez-vous à: [URL_OF_YOUR_SITE]/login/
        
        Bienvenue dans ENSA Project Manager!
        
        Cordialement,
        L'équipe ENSA Project Manager
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [registration.email],
            fail_silently=False,
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to send approval email to {registration.email}: {e}")
        return False