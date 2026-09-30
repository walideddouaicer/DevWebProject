from django.core import mail

from accounts.models import PendingRegistration

from .base import BrowserTestCase


class SignupApprovalLogin(BrowserTestCase):
    def test_signup_then_admin_approval_then_login(self):
        visitor = self.page()
        visitor.goto(self.url("/"))
        visitor.get_by_role("link", name="Créer un compte").first.click()
        visitor.get_by_role("link", name="Étudiant").first.click()
        self.field(visitor, "Prénom").fill("Nadia")
        self.field(visitor, "Nom").fill("Berrada")
        self.field(visitor, "Nom d'utilisateur").fill("nadia.b")
        self.field(visitor, "Adresse e-mail").fill("nadia@example.com")
        self.field(visitor, "Numéro d'étudiant").fill("E7777")
        self.field(visitor, "Année d'étude").select_option("3")
        self.field(visitor, "Filière").fill("Génie informatique")
        self.field(visitor, "Mot de passe").fill("Kenitra-2026-projet")
        self.field(visitor, "Confirmer le mot de passe").fill("Kenitra-2026-projet")
        visitor.get_by_role("button", name="Envoyer la demande").click()
        self.assertIn("Demande d'inscription envoyée", " ".join(self.toast(visitor)))
        self.assertTrue(PendingRegistration.objects.filter(username="nadia.b").exists())

        # Not active yet
        self.login(visitor, "nadia.b", "Kenitra-2026-projet")
        self.assertIn("/login/", visitor.url)

        admin = self.as_("admin")
        admin.get_by_role("link", name="Inscriptions").first.click()
        row = admin.locator("tr, li, article").filter(has_text="nadia.b").first
        row.get_by_role("button", name="Activer").click()
        admin.wait_for_load_state("networkidle")
        self.assertTrue(any("activé" in m.subject for m in mail.outbox))

        self.login(visitor, "nadia.b", "Kenitra-2026-projet")
        self.assertIn("/student/dashboard/", visitor.url)
