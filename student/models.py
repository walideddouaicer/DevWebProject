from django.db import models

# Create your models here.

class StudentProfile(models.Model):
    """Model for additional student profile information."""
    student = models.OneToOneField('accounts.Student', on_delete=models.CASCADE)
    # Add profile fields (year, major, etc.)
