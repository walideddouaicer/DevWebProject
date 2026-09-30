from django.template import Context, Template
from django.test import SimpleTestCase


class IconTagTests(SimpleTestCase):
    def render(self, source):
        return Template("{% load ui %}" + source).render(Context())

    def test_decorative_icon_is_hidden_from_assistive_tech(self):
        html = self.render('{% icon "bell" %}')
        self.assertIn('aria-hidden="true"', html)
        self.assertIn("sprite.svg#i-bell", html)

    def test_labelled_icon(self):
        html = self.render('{% icon "bell" label="Notifications <3" %}')
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
