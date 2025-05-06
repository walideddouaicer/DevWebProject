from django.db import models

# Create your models here.

class Project(models.Model):
    """Model representing a student project."""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('validated', 'Validated'),
        ('rejected', 'Rejected'),
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    # Add other fields (student, teacher, year, etc.)

    def __str__(self):
        return self.title

class Deliverable(models.Model):
    """Model representing a project deliverable (report, code, presentation, etc.)."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    file = models.FileField(upload_to='deliverables/')
    deliverable_type = models.CharField(max_length=50)
    # Add other fields as needed
