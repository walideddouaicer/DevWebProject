from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

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


# Module model - core of the system (ENHANCED)
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
    
    # NEW FIELDS for teacher assignment system
    primary_teacher = models.ForeignKey(
        'TeacherProfile', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='primary_modules',
        help_text="Main teacher responsible for this module"
    )
    
    classroom = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Physical classroom/location"
    )
    
    # Module creation permissions
    created_by_teacher = models.BooleanField(
        default=False,
        help_text="True if created by teacher, False if by admin"
    )
    
    requires_approval = models.BooleanField(
        default=True,
        help_text="Teacher-created modules need admin approval"
    )
    
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='approved_modules',
        help_text="Admin who approved this module"
    )
    
    approved_at = models.DateTimeField(null=True, blank=True)
    
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


# UPDATED: Core assignment system with team terminology
class ProjectAssignment(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='assignments')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='project_assignments')
    
    # Assignment details
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructions = models.TextField(blank=True, help_text="Detailed instructions for students")
    deadline = models.DateTimeField()
    
    # Assignment type
    ASSIGNMENT_TYPES = [
        ('direct', 'Direct Assignment'),
        ('choice_based', 'Choice-Based Assignment')
    ]
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPES)
    
    # UPDATED: Team work settings (renamed from group_work)
    is_team_work = models.BooleanField(default=False, help_text="Ce devoir doit-il être fait en équipe?")
    min_team_size = models.IntegerField(default=1, help_text="Taille minimale de l'équipe")
    max_team_size = models.IntegerField(default=1, help_text="Taille maximale de l'équipe")
    
    # For direct assignments
    target_selection = models.CharField(
        max_length=20,
        choices=[
            ('all_students', 'All Students in Module'),
            ('specific_students', 'Specific Students')
        ],
        default='all_students'
    )
    
    # Status and dates
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('in_progress', 'In Progress'), 
        ('completed', 'Completed')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    selection_deadline = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.module.code}"
    
    def clean(self):
        """Enhanced validation for deadlines and team settings"""
        super().clean()
        errors = {}
        
        # Validate deadlines are in chronological order
        now = timezone.now()
        
        if self.deadline and self.deadline <= now:
            errors['deadline'] = "La date limite doit être dans le futur."
        
        if self.assignment_type == 'choice_based':
            if self.selection_deadline:
                if self.selection_deadline <= now:
                    errors['selection_deadline'] = "La date limite de sélection doit être dans le futur."
                if self.deadline and self.selection_deadline >= self.deadline:
                    errors['selection_deadline'] = "La sélection des projets doit se terminer avant la date limite du projet."
        
        # Validate team sizes (updated field names)
        if self.is_team_work:
            if self.min_team_size and self.max_team_size:
                if self.min_team_size > self.max_team_size:
                    errors['min_team_size'] = "La taille minimale ne peut pas être supérieure à la taille maximale."
                if self.min_team_size < 2:
                    errors['min_team_size'] = "Pour un travail en équipe, la taille minimale doit être d'au moins 2."
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.clean()
        super().save(*args, **kwargs)
    
    def can_be_published(self):
        """Check if assignment is ready to be published"""
        if self.assignment_type == 'choice_based':
            return self.project_options.exists()
        # For direct assignments, allow publishing without pre-assigned students
        return True
    
    def get_total_students(self):
        """Get total number of students this assignment applies to"""
        if self.target_selection == 'all_students':
            return self.module.get_enrolled_students_count()
        else:
            return self.direct_assignments.count()
    
    def get_submitted_projects_count(self):
        """Count submitted projects for this assignment"""
        return self.submitted_projects.filter(status__in=['submitted', 'validated']).count()
    
    def get_completion_percentage(self):
        """Calculate completion percentage"""
        total = self.get_total_students()
        if total == 0:
            return 0
        submitted = self.get_submitted_projects_count()
        return int((submitted / total) * 100)
    
    def is_deadline_approaching(self, days=7):
        """Check if any deadline is approaching within specified days"""
        now = timezone.now()
        approaching_deadlines = []
        
        if self.selection_deadline and self.selection_deadline > now:
            days_left = (self.selection_deadline - now).days
            if days_left <= days:
                approaching_deadlines.append(('selection', days_left))
        
        if self.deadline and self.deadline > now:
            days_left = (self.deadline - now).days
            if days_left <= days:
                approaching_deadlines.append(('final', days_left))
        
        return approaching_deadlines

    def get_team_statistics(self):
        """Get statistics about teams formed for this assignment"""
        from student.models import Project
        
        assignment_projects = self.submitted_projects.all()
        
        total_projects = assignment_projects.count()
        total_students_in_teams = 0
        team_sizes = []
        
        for project in assignment_projects:
            team_size = project.get_team_size()
            team_sizes.append(team_size)
            total_students_in_teams += team_size
        
        # Calculate statistics
        stats = {
            'total_projects': total_projects,
            'total_students_in_teams': total_students_in_teams,
            'average_team_size': sum(team_sizes) / len(team_sizes) if team_sizes else 0,
            'min_team_size': min(team_sizes) if team_sizes else 0,
            'max_team_size': max(team_sizes) if team_sizes else 0,
            'team_size_distribution': {},
        }
        
        # Count distribution of team sizes
        for size in team_sizes:
            stats['team_size_distribution'][size] = stats['team_size_distribution'].get(size, 0) + 1
        
        return stats

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Project Assignment"
        verbose_name_plural = "Project Assignments"


# UPDATED: For choice-based assignments with team terminology
class ProjectOption(models.Model):
    assignment = models.ForeignKey(ProjectAssignment, on_delete=models.CASCADE, related_name='project_options')
    title = models.CharField(max_length=200)
    description = models.TextField()
    requirements = models.TextField(blank=True, help_text="Specific requirements or skills needed")
    estimated_difficulty = models.CharField(
        max_length=20,
        choices=[
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard')
        ],
        default='medium'
    )
    
    # UPDATED: Availability settings with team terminology
    is_unique = models.BooleanField(default=True, help_text="Only one team can choose this project")
    max_teams = models.IntegerField(default=1, help_text="Maximum teams if not unique")
    current_teams = models.IntegerField(default=0, help_text="Current number of teams assigned")
    
    # Ordering and status
    order = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.assignment.title}"
    
    def clean(self):
        """Validate project option settings"""
        super().clean()
        errors = {}
        
        if not self.is_unique and (not self.max_teams or self.max_teams < 1):
            errors['max_teams'] = "Pour un projet non unique, vous devez spécifier un nombre maximum d'équipes."
        
        if self.current_teams < 0:
            errors['current_teams'] = "Le nombre d'équipes actuelles ne peut pas être négatif."
        
        if not self.is_unique and self.current_teams > self.max_teams:
            errors['current_teams'] = "Le nombre d'équipes actuelles ne peut pas dépasser le maximum autorisé."
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.clean()
        super().save(*args, **kwargs)
    
    def is_selectable(self):
        """Check if this option can still be selected - thread-safe check"""
        if not self.is_available:
            return False
        if self.is_unique:
            return self.current_teams == 0
        return self.current_teams < self.max_teams
    
    @transaction.atomic
    def select_for_team(self, project):
        """Atomically select this option for a team (via project)"""
        # Refresh from database to get latest state
        option = ProjectOption.objects.select_for_update().get(id=self.id)
        
        if not option.is_selectable():
            raise ValidationError("Cette option de projet n'est plus disponible.")
        
        # Update counter atomically
        option.current_teams += 1
        option.save(update_fields=['current_teams'])
        
        # Update project
        project.selected_option = option
        project.save(update_fields=['selected_option'])
        
        return True
    
    @transaction.atomic
    def release_from_team(self, project):
        """Atomically release this option from a team (via project)"""
        # Refresh from database to get latest state
        option = ProjectOption.objects.select_for_update().get(id=self.id)
        
        if option.current_teams > 0:
            option.current_teams -= 1
            option.save(update_fields=['current_teams'])
        
        # Update project
        project.selected_option = None
        project.save(update_fields=['selected_option'])
    
    def get_availability_text(self):
        """Get human-readable availability status"""
        if not self.is_available:
            return "Non disponible"
        if self.is_unique:
            return "Disponible" if self.current_teams == 0 else "Pris"
        return f"{self.current_teams}/{self.max_teams} équipes"

    class Meta:
        ordering = ['order', 'title']
        verbose_name = "Project Option"
        verbose_name_plural = "Project Options"


# NEW MODEL: Direct student assignments with better tracking
class DirectStudentAssignment(models.Model):
    """Track individual students assigned to direct assignments"""
    assignment = models.ForeignKey(ProjectAssignment, on_delete=models.CASCADE, related_name='direct_assignments')
    student = models.ForeignKey('student.StudentProfile', on_delete=models.CASCADE, related_name='direct_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    # Status tracking with clear progression
    STATUS_CHOICES = [
        ('assigned', 'Assigné'),      # Initial state
        ('started', 'Commencé'),      # Student has created project
        ('submitted', 'Soumis'),      # Project submitted for review
        ('validated', 'Validé')       # Project validated by teacher
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.assignment.title}"
    
    def can_start_project(self):
        """Check if student can start working on the project"""
        return (
            self.status == 'assigned' and 
            self.assignment.status == 'published'
        )
    
    def is_overdue(self):
        """Check if assignment is overdue"""
        if self.status in ['submitted', 'validated']:
            return False
        return timezone.now() > self.assignment.deadline

    class Meta:
        unique_together = ('assignment', 'student')
        ordering = ['-assigned_at']
        verbose_name = "Direct Student Assignment"
        verbose_name_plural = "Direct Student Assignments"