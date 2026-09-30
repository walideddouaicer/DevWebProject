from django.template import Context, Template
from django.test import SimpleTestCase


class IconTagTests(SimpleTestCase):
    def render(self, source, **context):
        return Template("{% load ui %}" + source).render(Context(context))

    def test_decorative_icon_is_hidden_from_assistive_tech(self):
        html = self.render('{% icon "bell" %}')
        self.assertIn('aria-hidden="true"', html)
        self.assertIn("sprite.svg#i-bell", html)

    def test_labelled_icon(self):
        html = self.render('{% icon "bell" label=name %}', name="Notifications <3")
        self.assertIn('role="img"', html)
        self.assertIn("Notifications &lt;3", html)

    def test_every_listed_icon_is_in_the_sprite(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent / "static" / "icons"
        sprite = (root / "sprite.svg").read_text()
        names = [
            n.strip()
            for n in (root / "icons.txt").read_text().splitlines()
            if n.strip() and not n.startswith("#")
        ]
        for name in names:
            self.assertIn(f'id="i-{name}"', sprite)


class ComponentTagTests(SimpleTestCase):
    def render(self, source, **context):
        return Template("{% load ui %}" + source).render(Context(context))

    def test_status_chip_labels_and_tones(self):
        html = self.render('{% status_chip "revision_requested" %}')
        self.assertIn("chip-revision", html)
        self.assertIn("Révision demandée", html)

    def test_avatar_initials(self):
        from django.contrib.auth.models import User

        user = User(username="x", first_name="Amine", last_name="Berrada")
        html = self.render("{% avatar u %}", u=user)
        self.assertIn(">AB<", html)
        self.assertIn('aria-label="Amine Berrada"', html)

    def test_avatar_escapes_names(self):
        from django.contrib.auth.models import User

        html = self.render("{% avatar u %}", u=User(username="x", first_name="<b>x", last_name="y"))
        self.assertNotIn("<b>", html)

    def test_relative_days(self):
        from datetime import date

        from ui.templatetags.ui import relative_day

        today = date(2026, 10, 5)
        self.assertEqual(relative_day(date(2026, 10, 5), today)[0], "aujourd'hui")
        self.assertEqual(relative_day(date(2026, 10, 6), today)[0], "demain")
        self.assertEqual(relative_day(date(2026, 10, 8), today)[0], "dans 3 jours")
        self.assertEqual(relative_day(date(2026, 10, 3), today)[0], "il y a 2 jours")

    def test_deadline_urgency(self):
        from datetime import timedelta

        from django.utils import timezone

        soon = self.render("{% deadline d %}", d=timezone.now() + timedelta(days=1))
        late = self.render("{% deadline d %}", d=timezone.now() - timedelta(days=1))
        self.assertIn("is-soon", soon)
        self.assertIn("is-late", late)
