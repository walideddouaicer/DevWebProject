from django.db import models

# Create your models here.

class Student(models.Model):
    """Model representing a student user."""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    # Add student-specific fields here

class Teacher(models.Model):
    """Model representing a teacher user."""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    # Add teacher-specific fields here

class Administrator(models.Model):
    """Model representing an administrator user."""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    # Add administrator-specific fields here
