# administrator/models.py
from django.db import models
from django.contrib.auth.models import User

class AdminProfile(models.Model):
    """Administrator profile - similar to TeacherProfile but for admins"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    admin_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.CharField(max_length=100, default="Administration")
    role = models.CharField(max_length=50, default="Administrator", help_text="e.g., Administrator, Department Head, Academic Coordinator")
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.admin_id}) - {self.role}"

    class Meta:
        verbose_name = "Admin Profile"
        verbose_name_plural = "Admin Profiles"