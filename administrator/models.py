from django.db import models

# Create your models here.

class AdminProfile(models.Model):
    """Model for additional administrator profile information."""
    administrator = models.OneToOneField('accounts.Administrator', on_delete=models.CASCADE)
    # Add profile fields (role, permissions, etc.)
