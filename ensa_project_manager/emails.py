"""Plain-text emails rendered from templates/emails/*.txt (PLAN P2.7).

Every email that links back to the site uses settings.SITE_URL so links work from
a mail client (the old code had a literal "[URL_OF_YOUR_SITE]" placeholder).
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def absolute_url(name, *args):
    return f"{settings.SITE_URL}{reverse(name, args=args)}"


def send_templated_email(subject, template, context, recipients):
    """Render templates/emails/<template>.txt and send it. Returns True on success."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    body = render_to_string(f"emails/{template}.txt", {"site_url": settings.SITE_URL, **context})
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
    except Exception:
        logger.exception("Email %r to %s failed", template, recipients)
        return False
    return True
