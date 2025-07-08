from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
# Create your models here.


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    year_of_study = models.IntegerField(choices=[(3, '3rd Year'), (4, '4th Year'), (5, '5th Year')])
    department = models.CharField(max_length=100)
    
    # NEW PROFILE FIELDS - All optional
    bio = models.TextField(blank=True, null=True, help_text="Tell us about yourself")
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Your contact number")
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True, help_text="Profile photo")
    linkedin_url = models.URLField(blank=True, null=True, help_text="LinkedIn profile URL")
    github_url = models.URLField(blank=True, null=True, help_text="GitHub profile URL")
    personal_website = models.URLField(blank=True, null=True, help_text="Personal website or portfolio")
    
    # Profile completion tracking
    profile_updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.student_id}) - {self.department}"
    
    def get_profile_completion_percentage(self):
        """Calculate profile completion percentage"""
        total_fields = 9  # Total optional profile fields we track
        completed_fields = 0
        
        # Check basic required fields
        if self.user.first_name: completed_fields += 1
        if self.user.last_name: completed_fields += 1
        if self.user.email: completed_fields += 1
        
        # Check optional profile fields
        if self.bio: completed_fields += 1
        if self.phone_number: completed_fields += 1
        if self.profile_picture: completed_fields += 1
        if self.linkedin_url: completed_fields += 1
        if self.github_url: completed_fields += 1
        if self.personal_website: completed_fields += 1
        
        return int((completed_fields / total_fields) * 100)
    
    def get_avatar_url(self):
        """Get profile picture URL or return None for default avatar"""
        if self.profile_picture:
            return self.profile_picture.url
        return None
    
    def get_full_name(self):
        """Get user's full name or username as fallback"""
        return self.user.get_full_name() or self.user.username
    
    def get_display_name(self):
        """Get display name for UI"""
        if self.user.first_name or self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return self.user.username


# Project model
class Project(models.Model):
    PROJECT_TYPES = [
        ('stage_initiation', "Stage d'initiation (3ème année)"),
        ('stage_ingenieur', "Stage d'ingénieur adjoint (4ème année)"),
        ('stage_pfe', "Stage de fin d'études - PFE (5ème année)"),
        ('module', 'Projet de module'),
    ]
    
    STATUS_CHOICES = [
        ('in_progress', 'En cours'),  # Default status when created
        ('submitted', 'Soumis'),       # When student submits for review
        ('validated', 'Validé'),       # When teacher approves
        ('rejected', 'Rejeté'),        # When teacher rejects
    ]
    
    # Basic project information
    title = models.CharField(max_length=200)
    description = models.TextField()
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES)
    module_or_company = models.CharField(max_length=200, blank=True, null=True)
    student = models.ForeignKey('StudentProfile', on_delete=models.CASCADE, related_name='projects')
    collaborators = models.ManyToManyField('StudentProfile', blank=True, related_name='collaborated_projects')
    technologies = models.CharField(max_length=500, blank=True)  # Comma-separated list of technologies
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Module connection
    module = models.ForeignKey('teacher.Module', on_delete=models.SET_NULL, null=True, blank=True, 
                              related_name='projects', help_text="Module associé à ce projet")
    
    # ASSIGNMENT INTEGRATION FIELDS
    assignment_source = models.CharField(
        max_length=20, 
        choices=[
            ('student_initiated', 'Student Initiated'),
            ('teacher_assigned', 'Teacher Assigned')
        ],
        default='student_initiated'
    )
    
    # For teacher-assigned projects
    project_assignment = models.ForeignKey(
        'teacher.ProjectAssignment', 
        on_delete=models.CASCADE, 
        null=True, blank=True,
        related_name='submitted_projects'
    )
    
    selected_option = models.ForeignKey(
        'teacher.ProjectOption',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submitted_projects'
    )
    
    # Assignment submission tracking
    assignment_submitted_at = models.DateTimeField(null=True, blank=True)
    assignment_deadline = models.DateTimeField(null=True, blank=True)
    
    # Public showcase fields
    is_public = models.BooleanField(default=False, help_text="Project is visible on public showcase")
    made_public_at = models.DateTimeField(null=True, blank=True, help_text="When project was made public")
    public_cover_image = models.ImageField(upload_to='project_covers/', null=True, blank=True,
                                         help_text="Cover image for public display (optional)")
    public_description = models.TextField(blank=True, 
                                        help_text="Public description (falls back to main description if empty)")
    public_demo_url = models.URLField(blank=True, help_text="Live demo link")
    public_github_url = models.URLField(blank=True, help_text="GitHub repository")
    public_portfolio_url = models.URLField(blank=True, help_text="Portfolio/project page")
    
    # Engagement metrics
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    
    # Community moderation
    is_reported = models.BooleanField(default=False)
    report_count = models.PositiveIntegerField(default=0)
    is_hidden_by_admin = models.BooleanField(default=False, help_text="Hidden due to reports/violations")
    
    def __str__(self):
        return self.title
    
    def is_assignment_project(self):
        """Check if this is a teacher-assigned project"""
        return self.assignment_source == 'teacher_assigned' and self.project_assignment is not None

    def is_student_initiated(self):
        """Check if this is a student-initiated project"""
        return self.assignment_source == 'student_initiated'

    def get_team_members(self):
        """Get all team members (owner + collaborators) for this project"""
        team_members = [self.student]  # Project owner
        team_members.extend(list(self.collaborators.all()))  # Add collaborators
        return team_members

    def get_team_size(self):
        """Get current team size (owner + collaborators)"""
        return 1 + self.collaborators.count()

    def get_assignment_max_team_size(self):
        """Get maximum team size allowed by assignment"""
        if not self.is_assignment_project():
            return None  # No limit for personal projects
        
        assignment = self.project_assignment
        if not assignment.is_team_work:
            return 1  # Individual assignment
        
        return assignment.max_team_size

    def get_assignment_min_team_size(self):
        """Get minimum team size required by assignment"""
        if not self.is_assignment_project():
            return 1  # Personal projects default to 1
        
        assignment = self.project_assignment
        if not assignment.is_team_work:
            return 1  # Individual assignment
        
        return assignment.min_team_size

    def can_invite_more_collaborators(self):
        """Check if more collaborators can be invited based on assignment constraints"""
        if not self.is_assignment_project():
            return True  # Personal projects have no limits
        
        assignment = self.project_assignment
        
        # Individual assignments cannot have collaborators
        if not assignment.is_team_work:
            return False
        
        current_size = self.get_team_size()
        max_size = assignment.max_team_size
        
        return current_size < max_size

    def get_remaining_team_slots(self):
        """Get number of additional collaborators that can be invited"""
        if not self.is_assignment_project():
            return 999  # Unlimited for personal projects
        
        if not self.project_assignment.is_team_work:
            return 0  # No collaborators for individual assignments
        
        current_size = self.get_team_size()
        max_size = self.project_assignment.max_team_size
        
        return max(0, max_size - current_size)

    def is_team_size_valid(self):
        """Check if current team size meets assignment requirements"""
        if not self.is_assignment_project():
            return True  # Personal projects always valid
        
        assignment = self.project_assignment
        current_size = self.get_team_size()
        
        # FIXED: Use the new field names
        if hasattr(assignment, 'min_team_size'):
            # New field names
            min_size = assignment.min_team_size
            max_size = assignment.max_team_size
        else:
            # Fallback to old field names for backwards compatibility
            min_size = getattr(assignment, 'min_team_size', 1)
            max_size = getattr(assignment, 'max_team_size', 1)
        
        # Check minimum and maximum constraints
        if current_size < min_size:
            return False
        
        if current_size > max_size:
            return False
        
        return True

    def get_team_size_status(self):
        """Get human-readable team size status"""
        if not self.is_assignment_project():
            return {
                'status': 'unlimited',
                'message': 'Projet personnel - pas de limite de taille',
                'can_invite': True
            }
        
        assignment = self.project_assignment
        current_size = self.get_team_size()
        
        # FIXED: Use the new field names with fallback
        if hasattr(assignment, 'is_team_work'):
            is_team_work = assignment.is_team_work
            min_size = assignment.min_team_size
            max_size = assignment.max_team_size
        else:
            # Fallback to old field names
            is_team_work = getattr(assignment, 'is_team_work', False)
            min_size = getattr(assignment, 'min_team_size', 1)
            max_size = getattr(assignment, 'max_team_size', 1)
        
        if not is_team_work:
            return {
                'status': 'individual',
                'message': 'Devoir individuel - aucun collaborateur autorisé',
                'can_invite': False
            }
        
        if current_size < min_size:
            needed = min_size - current_size
            return {
                'status': 'too_small',
                'message': f'Il faut {needed} membre(s) de plus (minimum: {min_size})',
                'can_invite': True
            }
        elif current_size > max_size:
            excess = current_size - max_size
            return {
                'status': 'too_large', 
                'message': f'{excess} membre(s) en trop (maximum: {max_size})',
                'can_invite': False
            }
        elif current_size == max_size:
            return {
                'status': 'full',
                'message': f'Équipe complète ({current_size}/{max_size})',
                'can_invite': False
            }
        else:
            remaining = max_size - current_size
            return {
                'status': 'optimal',
                'message': f"Taille d'équipe OK ({current_size}/{max_size}) - peut inviter {remaining} de plus",
                'can_invite': True
            }

    def can_be_submitted_for_assignment(self):
        """Enhanced check for assignment submission eligibility"""
        if not self.is_assignment_project():
            return False
        
        # Must be in correct status
        if self.status in ['submitted', 'validated']:
            return False
        
        # Check deadline
        assignment = self.project_assignment
        deadline = assignment.deadline
        if deadline and timezone.now() > deadline:
            return False
        
        # Team size must be valid
        if not self.is_team_size_valid():
            return False
        
        # For choice-based assignments, must have selected option
        if assignment.assignment_type == 'choice_based':
            if not self.selected_option:
                return False
        
        return True

    def get_assignment_team_display(self):
        """Get formatted display of team members for assignment context"""
        if not self.is_assignment_project():
            return None
        
        team_members = self.get_team_members()
        
        if len(team_members) == 1:
            return f"Individuel: {team_members[0].get_full_name()}"
        
        owner_name = self.student.get_full_name()
        collaborator_names = [member.get_full_name() for member in team_members[1:]]
        
        if len(collaborator_names) == 1:
            return f"Équipe: {owner_name} & {collaborator_names[0]}"
        elif len(collaborator_names) == 2:
            return f"Équipe: {owner_name}, {collaborator_names[0]} & {collaborator_names[1]}"
        else:
            others_count = len(collaborator_names) - 1
            return f"Équipe: {owner_name}, {collaborator_names[0]} & {others_count} autres"

    def is_overdue(self):
        """Check if assignment project is overdue"""
        if self.assignment_deadline and self.status not in ['submitted', 'validated']:
            return timezone.now() > self.assignment_deadline
        return False
    
    def get_assignment_deadline(self):
        """Get the relevant deadline for this project"""
        if self.project_assignment:
            return self.project_assignment.deadline
        return self.assignment_deadline

    def get_assignment_team_info(self):
        """Get comprehensive team information for assignment context"""
        if not self.is_assignment_project():
            return None
            
        assignment = self.project_assignment
        team_members = self.get_team_members()
        
        return {
            'assignment': assignment,
            'is_team_work': assignment.is_team_work,
            'team_members': team_members,
            'team_size': len(team_members),
            'min_required': assignment.min_team_size,
            'max_allowed': assignment.max_team_size,
            'size_status': self.get_team_size_status(),
            'can_invite_more': self.can_invite_more_collaborators(),
            'remaining_slots': self.get_remaining_team_slots(),
            'is_valid_size': self.is_team_size_valid(),
            'can_submit': self.can_be_submitted_for_assignment(),
            'selected_option': self.selected_option,
            'display_name': self.get_assignment_team_display(),
        }

    def add_assignment_collaborator(self, student):
        """Add collaborator with assignment-specific validation"""
        if not self.is_assignment_project():
            # For non-assignment projects, use regular collaboration
            self.collaborators.add(student)
            return True
            
        assignment = self.project_assignment
        
        # Check if assignment allows collaboration
        if not assignment.is_team_work:
            raise ValidationError("Ce devoir doit être fait individuellement.")
        
        # Check team size limits
        if not self.can_invite_more_collaborators():
            size_status = self.get_team_size_status()
            raise ValidationError(f"Impossible d'ajouter des collaborateurs: {size_status['message']}")
        
        # Check if student is enrolled in the module
        if not student.module_enrollments.filter(
            module=assignment.module,
            is_active=True
        ).exists():
            raise ValidationError(f"{student.get_full_name()} n'est pas inscrit au module {assignment.module.code}.")
        
        # For direct assignments, check if student is also assigned
        if assignment.assignment_type == 'direct':
            from teacher.models import DirectStudentAssignment
            if not DirectStudentAssignment.objects.filter(
                assignment=assignment,
                student=student
            ).exists():
                raise ValidationError(f"{student.get_full_name()} n'est pas assigné à ce devoir.")
        
        # Check if student is already working on this assignment
        existing_project = Project.objects.filter(
            project_assignment=assignment
        ).filter(
            Q(student=student) | Q(collaborators=student)
        ).exclude(id=self.id).first()
        
        if existing_project:
            raise ValidationError(f"{student.get_full_name()} travaille déjà sur ce devoir dans le projet '{existing_project.title}'.")
        
        # Add the collaborator
        self.collaborators.add(student)
        return True

    def remove_assignment_collaborator(self, student):
        """Remove collaborator with assignment-specific checks"""
        if student == self.student:
            raise ValidationError("Le propriétaire du projet ne peut pas être retiré.")
        
        if not self.collaborators.filter(id=student.id).exists():
            raise ValidationError("Cet étudiant n'est pas un collaborateur du projet.")
        
        # For assignment projects, check if removal would violate size constraints
        if self.is_assignment_project():
            assignment = self.project_assignment
            new_size = self.get_team_size() - 1
            
            if new_size < assignment.min_team_size:
                raise ValidationError(f"Impossible de retirer ce collaborateur: l'équipe serait trop petite (minimum: {assignment.min_team_size}).")
        
        self.collaborators.remove(student)
        return True
    
    def calculate_progress(self):
        """Calculate detailed project progress based on multiple factors"""
        progress_components = {
            'status': 0,
            'milestones': 0,
            'deliverables': 0,
            'time': 0
        }
        
        # Status-based progress (30% weight)
        status_weights = {
            'in_progress': 50,
            'submitted': 80,
            'validated': 100,
            'rejected': 20
        }
        progress_components['status'] = status_weights.get(self.status, 0) * 0.3
        
        # Milestone completion (40% weight)
        total_milestones = self.milestones.count()
        if total_milestones > 0:
            completed_milestones = self.milestones.filter(completed=True).count()
            progress_components['milestones'] = (completed_milestones / total_milestones) * 100 * 0.4
        else:
            progress_components['milestones'] = 20
        
        # Deliverables (20% weight)
        deliverable_count = self.deliverables.count()
        deliverable_progress = min(deliverable_count / 3 * 100, 100)
        progress_components['deliverables'] = deliverable_progress * 0.2
        
        # Time progress (10% weight)
        if self.start_date and self.end_date:
            total_duration = (self.end_date - self.start_date).days
            elapsed = (timezone.now().date() - self.start_date).days
            if total_duration > 0:
                time_progress = min(elapsed / total_duration * 100, 100)
                progress_components['time'] = time_progress * 0.1
        else:
            progress_components['time'] = 5
        
        # Calculate total progress
        total_progress = sum(progress_components.values())
        return {
            'total': round(total_progress),
            'components': progress_components,
            'is_on_track': self.is_on_track()
        }

    def is_on_track(self):
        """Determine if project is on track based on milestones and deadlines"""
        if not self.end_date:
            return True
        
        days_until_deadline = (self.end_date - timezone.now().date()).days
        
        # Check overdue milestones
        overdue_milestones = self.milestones.filter(
            completed=False,
            due_date__lt=timezone.now().date()
        ).count()
        
        if overdue_milestones > 0:
            return False
        
        # Check if we're in the last 20% of time with less than 80% progress
        if self.start_date:
            total_duration = (self.end_date - self.start_date).days
            if total_duration > 0:
                time_remaining_percent = (days_until_deadline / total_duration) * 100
                if time_remaining_percent < 20 and self.calculate_progress()['total'] < 80:
                    return False
        
        return True
    
    def can_be_made_public(self):
        """Check if project is eligible for public showcase"""
        return (
            self.status == 'validated' and 
            not self.is_hidden_by_admin
        )
    
    def make_public(self):
        """Make project public instantly"""
        if self.can_be_made_public():
            self.is_public = True
            self.made_public_at = timezone.now()
            self.save(update_fields=['is_public', 'made_public_at'])
            return True
        return False
    
    def make_private(self):
        """Remove from public showcase"""
        self.is_public = False
        self.save(update_fields=['is_public'])
    
    @property
    def display_description(self):
        """Return public description or fall back to main description"""
        return self.public_description or self.description
    
    @property
    def has_public_content(self):
        """Check if project has enhanced public content"""
        return bool(self.public_cover_image or self.public_description or 
                   self.public_demo_url or self.public_github_url)

    def update_like_count(self):
        """Update cached like count"""
        self.like_count = self.public_likes.count()
        self.save(update_fields=['like_count'])

    class Meta:
        ordering = ['-created_at']


# Project Deliverable model
class ProjectDeliverable(models.Model):
    DELIVERABLE_TYPES = [
        ('report', 'Rapport'),
        ('presentation', 'Présentation'),
        ('source_code', 'Code source'),
        ('other', 'Autre'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='deliverables')
    file = models.FileField(upload_to='deliverables/')
    file_type = models.CharField(max_length=20, choices=DELIVERABLE_TYPES)
    name = models.CharField(max_length=200)
    upload_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.project.title}"


class ProjectMilestone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_milestones')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def is_overdue(self):
        """Check if milestone is overdue"""
        if self.completed:
            return False
        return timezone.now().date() > self.due_date
    
    class Meta:
        ordering = ['due_date']


# Collab Invitations
class CollaborationInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('accepted', 'Acceptée'),
        ('rejected', 'Refusée'),
        ('expired', 'Expirée'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invitations')
    sender = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='sent_invitations')
    recipient = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='received_invitations')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('project', 'recipient')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invitation from {self.sender} to {self.recipient} for {self.project}"


# notifications
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('invitation', 'Invitation de collaboration'),
        ('project_update', 'Mise à jour du projet'),
        ('milestone', 'Jalon ajouté'),
        ('deliverable', 'Livrable ajouté'),
        # NEW: Assignment-related notifications
        ('assignment_created', 'Nouveau devoir assigné'),
        ('assignment_deadline', 'Rappel de date limite'),
        ('group_invitation', 'Invitation de groupe'),
        ('project_selection', 'Sélection de projet'),
        ('assignment_feedback', 'Commentaire sur devoir'),
    ]
    
    recipient = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='notifications')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    # NEW: Link to assignment for assignment-related notifications
    project_assignment = models.ForeignKey('teacher.ProjectAssignment', on_delete=models.CASCADE, 
                                         related_name='notifications', null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.recipient}: {self.message[:30]}..."


# project activity
class ProjectActivity(models.Model):
    ACTIVITY_TYPES = [
        ('created', 'Création du projet'),
        ('status_changed', 'Changement de statut'),
        ('collaborator_added', 'Ajout de collaborateur'),
        ('collaborator_removed', 'Retrait de collaborateur'),
        ('milestone_added', 'Ajout de jalon'),
        ('milestone_completed', 'Jalon complété'),
        ('deliverable_added', 'Ajout de livrable'),
        # NEW: Add these activity types for public showcase
        ('made_public', 'Projet rendu public'),
        ('made_private', 'Projet retiré du public'),
        ('comment_added', 'Commentaire ajouté'),
        # NEW: Assignment-related activities
        ('assignment_created', 'Devoir créé depuis assignation'),
        ('assignment_submitted', 'Devoir soumis'),
        ('assignment_validated', 'Devoir validé'),
        ('assignment_rejected', 'Devoir rejeté'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.activity_type} on {self.project} by {self.user}"


# comments
class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # Changed from StudentProfile to User
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.author} on {self.project}"
    
    @property
    def is_teacher_comment(self):
        """Check if this comment was made by a teacher"""
        try:
            from teacher.models import TeacherProfile
            TeacherProfile.objects.get(user=self.author)
            return True
        except TeacherProfile.DoesNotExist:
            return False
    
    @property
    def author_profile(self):
        """Get the appropriate profile (StudentProfile or TeacherProfile) for the author"""
        if self.is_teacher_comment:
            from teacher.models import TeacherProfile
            try:
                return TeacherProfile.objects.get(user=self.author)
            except TeacherProfile.DoesNotExist:
                return None
        else:
            try:
                return StudentProfile.objects.get(user=self.author)
            except StudentProfile.DoesNotExist:
                return None


# 3. 
class ShowcaseTag(models.Model):
    """Tags for categorizing public projects"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']


class ProjectShowcaseTag(models.Model):
    """Many-to-many through table for project tags"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='showcase_tags')
    tag = models.ForeignKey(ShowcaseTag, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('project', 'tag')


class ProjectLike(models.Model):
    """Like system for public projects"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='public_likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='liked_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('project', 'user')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} likes {self.project.title}"


class PublicProjectComment(models.Model):
    """Public comments system (separate from internal project comments)"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='public_comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    
    # Simple moderation
    is_flagged = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)  # Auto-approve by default
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.project.title}"
    
    @property
    def author_profile(self):
        """Get the appropriate profile for the comment author"""
        # Try to get student profile first
        try:
            return StudentProfile.objects.get(user=self.author)
        except StudentProfile.DoesNotExist:
            pass
        
        # Try teacher profile
        try:
            from teacher.models import TeacherProfile
            return TeacherProfile.objects.get(user=self.author)
        except:
            pass
        
        return None


class ProjectView(models.Model):
    """Track public project views"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='public_views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Null for anonymous
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-viewed_at']


class ProjectReport(models.Model):
    """Community reporting system for inappropriate projects"""
    REPORT_REASONS = [
        ('inappropriate', 'Contenu inapproprié'),
        ('spam', 'Spam'),
        ('copyright', 'Violation de droits d\'auteur'),
        ('false_info', 'Informations fausses'),
        ('other', 'Autre'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    description = models.TextField(help_text="Description détaillée du problème")
    created_at = models.DateTimeField(auto_now_add=True)
    is_reviewed = models.BooleanField(default=False)
    admin_notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('project', 'reporter')  # One report per user per project
    
    def __str__(self):
        return f"Report by {self.reporter.username} on {self.project.title}"


class UserPreferences(models.Model):
    """Store user preferences and settings"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    project_notifications = models.BooleanField(default=True)
    collaboration_notifications = models.BooleanField(default=True)
    # NEW: Assignment notification preferences
    assignment_notifications = models.BooleanField(default=True)
    assignment_reminders = models.BooleanField(default=True)
    group_notifications = models.BooleanField(default=True)
    
    # Other preferences
    theme_preference = models.CharField(
        max_length=20, 
        choices=[('light', 'Clair'), ('dark', 'Sombre'), ('auto', 'Automatique')],
        default='auto'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"