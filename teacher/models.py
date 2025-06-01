from django.db import models
from django.contrib.auth.models import User

# Teacher Profile model - similar to StudentProfile
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    teacher_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.CharField(max_length=100, default="Unknown Department")
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.teacher_id}) - {self.department}"

    class Meta:
        verbose_name = "Teacher Profile"
        verbose_name_plural = "Teacher Profiles"


# Module model - core of the system
class Module(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, unique=True, help_text="Unique code for students to join (e.g., CS101, MATH204)")
    description = models.TextField(blank=True)
    academic_year = models.CharField(max_length=9, default="2024-2025", help_text="e.g., 2024-2025")
    semester = models.CharField(max_length=20, choices=[
        ('S1', 'Semestre 1'),
        ('S2', 'Semestre 2'),
        ('Summer', 'Session d\'été'),
    ], default='S1')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_enrolled_students_count(self):
        return self.enrollments.filter(is_active=True).count()
    
    def get_assigned_teachers_count(self):
        return self.assignments.filter(is_active=True).count()

    class Meta:
        ordering = ['code']


# Teacher-Module Assignment (many-to-many through table)
class ModuleAssignment(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='module_assignments')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, help_text="Administrator who made the assignment")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('teacher', 'module')
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.module.code}"


# Student-Module Enrollment (many-to-many through table)
class ModuleEnrollment(models.Model):
    student = models.ForeignKey('student.StudentProfile', on_delete=models.CASCADE, related_name='module_enrollments')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('student', 'module')
        ordering = ['-enrolled_at']
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.module.code}"