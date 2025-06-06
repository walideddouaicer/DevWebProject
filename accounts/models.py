from django.db import models
from django.contrib.auth.models import User

class PendingRegistration(models.Model):
    """Store pending registrations until admin approval"""
    ROLE_CHOICES = [
        ('student', 'Étudiant'),
        ('teacher', 'Enseignant'),
        ('administrator', 'Administrateur'),
    ]
    
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)  # Will be hashed
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Role-specific fields
    student_id = models.CharField(max_length=20, blank=True, null=True)
    teacher_id = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    year_of_study = models.IntegerField(null=True, blank=True)
    
    # Status tracking
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.role}"


# ============================================
# FORMS FOR SIGNUP
# ============================================


