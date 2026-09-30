"""Private deliverable downloads (PLAN P1.7)."""

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from student.forms import StudentProfileForm
from student.models import ProjectDeliverable

from .test_regressions import Fixtures


class DownloadTests(Fixtures):
    def setUp(self):
        s = self.students
        self.project = self.project(s[0], [s[1]])
        self.deliverable = ProjectDeliverable(
            project=self.project, name="Rapport final", file_type="report"
        )
        self.deliverable.file.save("rapport.pdf", ContentFile(b"%PDF-1.4 demo"), save=True)
        self.url = self.deliverable.download_url

    def status_for(self, user=None):
        self.client.logout()
        if user:
            self.client.force_login(user)
        return self.client.get(self.url).status_code

    def test_team_teacher_and_admin_can_download(self):
        for profile in (self.students[0], self.students[1], self.teacher, self.admin):
            self.assertEqual(self.status_for(profile.user), 200, profile)

    def test_others_get_404(self):
        self.assertEqual(self.status_for(None), 404)
        self.assertEqual(self.status_for(self.students[2].user), 404)
        self.assertEqual(self.status_for(self.other_teacher.user), 404)

    def test_download_is_an_attachment_with_nosniff(self):
        self.client.force_login(self.students[0].user)
        response = self.client.get(self.url)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("rapport-final-v1.pdf", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 demo")

    def test_inline_preview_only_for_previewable_files(self):
        self.client.force_login(self.students[0].user)
        response = self.client.get(self.url + "?inline=1")
        self.assertIn("inline", response["Content-Disposition"])
        archive = ProjectDeliverable(project=self.project, name="Code", file_type="source_code")
        archive.file.save("code.zip", ContentFile(b"PK"), save=True)
        self.assertIsNone(archive.preview_url)
        response = self.client.get(archive.download_url + "?inline=1")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_public_download_requires_owner_opt_in(self):
        self.project.status = "validated"
        self.project.is_public = True
        self.project.save()
        self.assertEqual(self.status_for(None), 404)
        self.project.public_deliverables = True
        self.project.save()
        self.assertEqual(self.status_for(None), 200)
        self.project.is_hidden_by_admin = True
        self.project.save()
        self.assertEqual(self.status_for(None), 404)

    def test_public_page_hides_files_without_opt_in(self):
        self.project.status = "validated"
        self.project.is_public = True
        self.project.save()
        page = self.client.get(reverse("public:project_detail", args=[self.project.id]))
        self.assertNotContains(page, self.url)
        self.project.public_deliverables = True
        self.project.save()
        page = self.client.get(reverse("public:project_detail", args=[self.project.id]))
        self.assertContains(page, self.url)

    def test_fake_image_is_rejected(self):
        form = StudentProfileForm(
            data={},
            files={
                "profile_picture": SimpleUploadedFile(
                    "avatar.png", b"<script>alert(1)</script>", content_type="image/png"
                )
            },
            instance=self.students[0],
            user=User.objects.get(pk=self.students[0].user_id),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("profile_picture", form.errors)

    def test_inline_preview_can_be_framed_by_our_pages_only(self):
        self.client.force_login(self.students[0].user)
        inline = self.client.get(self.url + "?inline=1")
        self.assertEqual(inline["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", inline["Content-Security-Policy-Report-Only"])
        attachment = self.client.get(self.url)
        self.assertEqual(attachment["X-Frame-Options"], "DENY")

    def test_pages_carry_a_csp(self):
        response = self.client.get("/")
        policy = response["Content-Security-Policy-Report-Only"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
