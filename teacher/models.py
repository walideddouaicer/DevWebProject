from django.db import models

# Create your models here.

class TeacherProfile(models.Model):
    """Model for additional teacher profile information."""
    teacher = models.OneToOneField('accounts.Teacher', on_delete=models.CASCADE)
    # Add profile fields (department, specialty, etc.)
