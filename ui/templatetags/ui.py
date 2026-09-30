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
