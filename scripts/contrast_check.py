"""WCAG contrast check for the design tokens (PLAN §6.3).

    .venv/bin/python scripts/contrast_check.py      # exit 1 if any pair fails

Reads the light (:root) and dark (:root[data-theme="dark"]) blocks of 01-tokens.css.
"""

import re
import sys
from pathlib import Path

TOKENS = Path(__file__).resolve().parent.parent / "assets/css/01-tokens.css"

# (foreground, background, minimum ratio, what it is)
PAIRS = [
    ("ink", "paper", 4.5, "body text"),
    ("ink", "surface", 4.5, "body text on cards"),
    ("ink-2", "paper", 4.5, "secondary text"),
    ("ink-2", "surface", 4.5, "secondary text on cards"),
    ("ink-2", "sunken", 4.5, "table header text"),
    ("ink-3", "surface", 4.5, "placeholders / meta"),
    ("ink-3", "paper", 4.5, "meta on paper"),
    ("danger-ink", "danger", 4.5, "solid danger button"),
    ("accent", "surface", 4.5, "links"),
    ("accent", "paper", 4.5, "links on paper"),
    ("accent-ink", "accent", 4.5, "primary button text"),
    ("accent", "accent-soft", 4.5, "selected nav item"),
    ("border-input", "surface", 3.0, "input borders (1.4.11)"),
    ("ok", "ok-soft", 4.5, "validated chip"),
    ("warn", "warn-soft", 4.5, "submitted chip"),
    ("danger", "danger-soft", 4.5, "rejected chip"),
    ("info", "info-soft", 4.5, "in-progress chip"),
    ("revision", "revision-soft", 4.5, "revision chip"),
    ("danger", "surface", 4.5, "error text"),
    ("ok", "surface", 4.5, "success text"),
    ("warn", "surface", 4.5, "warning text"),
]


def block(css, selector):
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def tokens(text):
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", text))


def luminance(hex_color):
    def channel(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(hex_color[i : i + 2]) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


css = TOKENS.read_text()
themes = {
    "light": tokens(block(css, ":root")),
    "dark": tokens(block(css, ':root[data-theme="dark"]')),
}
failures = 0
for theme, values in themes.items():
    for fg, bg, minimum, what in PAIRS:
        r = ratio(values[fg], values[bg])
        ok = r >= minimum
        failures += not ok
        print(
            f"{'ok  ' if ok else 'FAIL'} {theme:5} {fg:>12} on {bg:<13} {r:5.2f} (>= {minimum}) {what}"
        )
sys.exit(1 if failures else 0)
