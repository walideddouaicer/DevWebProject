"""Design-system template tags (PLAN P5.3+)."""

from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, label="", size=20, css=""):
    """Inline Lucide icon from the sprite.

    {% icon "bell" %}                        decorative (aria-hidden)
    {% icon "bell" label="Notifications" %}  meaningful on its own (role=img + title)
    """
    href = f"{static('icons/sprite.svg')}#i-{name}"
    classes = f"icon {css}".strip()
    if label:
        return format_html(
            '<svg class="{}" width="{}" height="{}" role="img" aria-label="{}" focusable="false">'
            '<title>{}</title><use href="{}"></use></svg>',
            classes,
            size,
            size,
            label,
            label,
            href,
        )
    return format_html(
        '<svg class="{}" width="{}" height="{}" aria-hidden="true" focusable="false">'
        '<use href="{}"></use></svg>',
        classes,
        size,
        size,
        href,
    )


# --------------------------------------------------------------------- status chips

STATUS_TONES = {
    # projects
    "in_progress": ("info", "En cours"),
    "submitted": ("warn", "Soumis"),
    "revision_requested": ("revision", "Révision demandée"),
    "validated": ("ok", "Validé"),
    "rejected": ("danger", "Rejeté"),
    # assignments
    "draft": ("", "Brouillon"),
    "published": ("accent", "Publié"),
    "completed": ("ok", "Terminé"),
    # direct assignment tracking
    "assigned": ("", "Assigné"),
    "started": ("info", "Commencé"),
    # invitations
    "pending": ("warn", "En attente"),
    "accepted": ("ok", "Acceptée"),
    "expired": ("", "Expirée"),
}


@register.simple_tag
def status_chip(status, label=""):
    """{% status_chip project.status %} -> colored chip with the French label."""
    tone, default_label = STATUS_TONES.get(status, ("", status))
    css = f"chip chip-{tone}" if tone else "chip"
    return format_html('<span class="{}">{}</span>', css, label or default_label)


# --------------------------------------------------------------------------- avatars


def _person(obj):
    """(display name, image url or None) for a User or a *Profile."""
    user = getattr(obj, "user", obj)
    name = ""
    if user is not None:
        name = user.get_full_name() or user.get_username()
    picture = getattr(obj, "profile_picture", None)
    url = picture.url if picture else None
    return name or "?", url


def initials(name):
    parts = [p for p in name.replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@register.simple_tag
def avatar(person, size="", label=True):
    """{% avatar student size="sm" %}: photo if any, else initials on a muted tone."""
    name, url = _person(person)
    tone = sum(ord(c) for c in name) % 6
    css = f"avatar avatar-{size}" if size else "avatar"
    if url:
        return format_html(
            '<span class="{}"><img src="{}" alt="{}"></span>', css, url, name if label else ""
        )
    if label:
        return format_html(
            '<span class="{}" data-tone="{}" role="img" aria-label="{}">{}</span>',
            css,
            tone,
            name,
            initials(name),
        )
    return format_html(
        '<span class="{}" data-tone="{}" aria-hidden="true">{}</span>', css, tone, initials(name)
    )


# ------------------------------------------------------------------------- deadlines


def relative_day(value, now=None):
    """French relative wording for a date/datetime: 'aujourd'hui', 'dans 3 jours', 'il y a 2 jours'."""
    from datetime import date, datetime

    from django.utils import timezone

    now = now or timezone.localtime()
    if isinstance(value, datetime):
        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    today = now.date() if isinstance(now, datetime) else now
    delta = (value - today).days if isinstance(value, date) else 0
    if delta == 0:
        return "aujourd'hui", delta
    if delta == 1:
        return "demain", delta
    if delta == -1:
        return "hier", delta
    if delta > 1:
        return (f"dans {delta} jours" if delta < 60 else f"dans {delta // 30} mois"), delta
    return (f"il y a {-delta} jours" if delta > -60 else f"il y a {-delta // 30} mois"), delta


@register.simple_tag
def deadline(value, done=False, soon_days=3):
    """{% deadline assignment.deadline %}: relative wording, exact date in a tooltip, urgency color."""
    from django.utils import formats, timezone

    if not value:
        return ""
    wording, delta = relative_day(value)
    local = (
        timezone.localtime(value) if hasattr(value, "hour") and timezone.is_aware(value) else value
    )
    exact = formats.date_format(
        local, "DATETIME_FORMAT" if hasattr(local, "hour") else "DATE_FORMAT"
    )
    state = (
        "is-done"
        if done
        else ("is-late" if delta < 0 else ("is-soon" if delta <= soon_days else ""))
    )
    return format_html(
        '<time class="deadline {}" datetime="{}" title="{}">{}{}</time>',
        state,
        local.isoformat(),
        exact,
        icon("clock", size=14),
        wording,
    )


# ---------------------------------------------------------------------------- forms


@register.inclusion_tag("components/field.html")
def field(bound_field, label="", help="", hide_label=False):
    """{% field form.title %}: label, control, help text and errors wired with aria attributes."""
    widget = bound_field.field.widget
    describedby = []
    if help or bound_field.help_text:
        describedby.append(f"{bound_field.auto_id}_help")
    if bound_field.errors:
        describedby.append(f"{bound_field.auto_id}_errors")
    attrs = {}
    if describedby:
        attrs["aria-describedby"] = " ".join(describedby)
    if bound_field.errors:
        attrs["aria-invalid"] = "true"
    input_type = getattr(widget, "input_type", "")
    return {
        "bf": bound_field,
        "control": bound_field.as_widget(attrs=attrs),
        "label": label or bound_field.label,
        "help": help or bound_field.help_text,
        "hide_label": hide_label,
        "is_check": input_type == "checkbox",
        "required": bound_field.field.required and input_type != "checkbox",
    }
