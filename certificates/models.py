from django.db import models

# Create your models here.

class Certificate(models.Model):
    """Model representing a generated certificate for a project or student."""
    student = models.ForeignKey('accounts.Student', on_delete=models.CASCADE)
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE)
    issued_at = models.DateTimeField(auto_now_add=True)
    # Add other fields as needed
