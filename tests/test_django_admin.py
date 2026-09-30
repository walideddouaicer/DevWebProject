"""Django admin back office (PLAN P4.9): every registered model's pages render."""

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class DjangoAdminTests(TestCase):
    def test_admin_is_not_at_the_default_url(self):
        self.assertNotEqual(reverse("admin:index"), "/admin/")
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_every_changelist_and_add_page_renders(self):
        superuser = User.objects.create_superuser("root", "root@example.com", "x")
        self.client.force_login(superuser)
        for model in admin.site._registry:
            meta = model._meta
            # django-axes logs are read-only by design (no add page)
            views = ("changelist",) if meta.app_label == "axes" else ("changelist", "add")
            for view in views:
                url = reverse(f"admin:{meta.app_label}_{meta.model_name}_{view}")
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
