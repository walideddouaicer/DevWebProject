"""Public site interactions (PLAN P6.2)."""

from django.urls import reverse

from student.models import PublicProjectComment

from .test_regressions import Fixtures


class PublicInteractionTests(Fixtures):
    def setUp(self):
        self.public = self.project(self.students[0], status="validated", is_public=True)
        self.url = reverse("public:toggle_project_like", args=[self.public.id])

    def test_like_without_javascript_redirects_back(self):
        self.login(self.students[1])
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("public:project_detail", args=[self.public.id]))
        self.public.refresh_from_db()
        self.assertEqual(self.public.like_count, 1)

    def test_like_with_htmx_returns_button(self):
        self.login(self.students[1])
        response = self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Vous aimez")
        response = self.client.post(self.url, HTTP_HX_REQUEST="true")  # toggles back
        self.assertContains(response, "J'aime")

    def test_like_json_api_kept(self):
        self.login(self.students[1])
        response = self.client.post(self.url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.json(), {"liked": True, "like_count": 1})

    def test_htmx_comment_returns_thread(self):
        self.login(self.students[1])
        response = self.client.post(
            reverse("public:add_project_comment", args=[self.public.id]),
            {"content": "Très beau travail"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "Très beau travail")
        self.assertEqual(PublicProjectComment.objects.count(), 1)

    def test_features_page_redirects_to_about(self):
        response = self.client.get(reverse("public:features"))
        self.assertRedirects(response, reverse("public:about"), status_code=301)
