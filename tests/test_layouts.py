"""Layouts, navigation and theme preference (PLAN P5.6/P5.7)."""

from django.template import RequestContext, Template
from django.test import RequestFactory
from django.urls import reverse

from student.models import UserPreferences
from ui.navigation import build_navigation

from .test_regressions import Fixtures


class LayoutTests(Fixtures):
    def render(self, profile, layout, path="/"):
        request = RequestFactory().get(path)
        request.user = type(profile.user).objects.get(pk=profile.user_id) if profile else None
        if request.user is None:
            from django.contrib.auth.models import AnonymousUser

            request.user = AnonymousUser()
        from django.contrib.messages.storage.fallback import FallbackStorage

        request.session = {}
        request._messages = FallbackStorage(request)
        template = Template(
            f'{{% extends "{layout}" %}}{{% block content %}}<p>page</p>{{% endblock %}}'
        )
        return template.render(RequestContext(request))

    def test_app_layout_renders_for_every_role(self):
        for profile, expected in [
            (self.students[0], "Espace étudiant"),
            (self.teacher, "Espace enseignant"),
            (self.admin, "Administration"),
        ]:
            html = self.render(profile, "layouts/app.html")
            self.assertIn(expected, html)
            self.assertIn('href="#main"', html)
            self.assertNotIn(" style=", html)  # CSP: no inline styles in the shell

    def test_public_and_auth_layouts(self):
        public = self.render(None, "layouts/public.html")
        self.assertIn("Créer un compte", public)
        auth = self.render(None, "layouts/auth.html")
        self.assertIn("<p>page</p>", auth)

    def test_exactly_one_current_nav_item(self):
        nav = build_navigation("student", "/student/projects/12/", {})
        current = [i["label"] for g in nav for i in g["items"] if i.get("current")]
        self.assertEqual(current, ["Mes projets"])
        nav = build_navigation("teacher", "/teacher/modules/3/projects/", {})
        current = [i["label"] for g in nav for i in g["items"] if i.get("current")]
        self.assertEqual(current, ["Modules"])

    def test_theme_preference_endpoint(self):
        url = reverse("ui:set_theme")
        self.assertEqual(self.client.post(url, {"theme": "dark"}).status_code, 302)  # login
        self.login(self.teacher)
        self.assertEqual(self.client.post(url, {"theme": "neon"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"theme": "dark"}).status_code, 204)
        self.assertEqual(
            UserPreferences.objects.get(user=self.teacher.user).theme_preference, "dark"
        )
        html = self.render(self.teacher, "layouts/app.html")
        self.assertIn('data-theme="dark"', html)
