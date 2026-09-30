"""Transactional emails rendered from templates/emails/ (PLAN P2.7, P6.12).

Each email has a plain-text body (``<name>.txt``) and, optionally, an HTML alternative
(``<name>.html`` extending ``emails/base.html``). Links use settings.SITE_URL so they work
from a mail client.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def absolute_url(name, *args):
    return f"{settings.SITE_URL}{reverse(name, args=args)}"


def render_email(template, context):
    """(text, html or None) for templates/emails/<template>.{txt,html}."""
    context = {"site_url": settings.SITE_URL, **context}
    text = render_to_string(f"emails/{template}.txt", context)
    try:
        html = render_to_string(f"emails/{template}.html", context)
    except TemplateDoesNotExist:
        html = None
    return text, html


def send_templated_email(subject, template, context, recipients):
    """Render and send one email (text + HTML alternative). Returns True on success."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    text, html = render_email(template, context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, recipients)
    if html:
        message.attach_alternative(html, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Email %r to %s failed", template, recipients)
        return False
    return True


def wants_email(user, category):
    """Should ``user`` get an immediate email of this category?

    ``category`` is a UserPreferences flag (project_notifications, collaboration_notifications,
    assignment_reminders...). Digest users get a daily summary instead of immediate emails.
    Users without a preferences row get the defaults (everything on, no digest).
    """
    if not user.email or not user.is_active:
        return False
    prefs = getattr(user, "preferences", None)
    if prefs is None:
        return True
    return prefs.email_notifications and getattr(prefs, category) and not prefs.email_digest
