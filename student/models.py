from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
# Create your models here.


# Student Profile model
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    year_of_study = models.IntegerField(choices=[(3, '3rd Year'), (4, '4th Year'), (5, '5th Year')])
    department = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.student_id}) - {self.department}"
    







# Project model
class Project(models.Model):
    PROJECT_TYPES = [
        ('stage_initiation', 'Stage d\'initiation (3ème année)'),
        ('stage_ingenieur', 'Stage d\'ingénieur adjoint (4ème année)'),
        ('stage_pfe', 'Stage de fin d\'études - PFE (5ème année)'),
        ('module', 'Projet de module'),
    ]
    
    STATUS_CHOICES = [
        ('in_progress', 'En cours'),  # Default status when created
        ('submitted', 'Soumis'),       # When student submits for review
        ('validated', 'Validé'),       # When teacher approves
        ('rejected', 'Rejeté'),        # When teacher rejects
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES)
    module_or_company = models.CharField(max_length=200, blank=True, null=True)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='projects')
    collaborators = models.ManyToManyField(StudentProfile, blank=True, related_name='collaborated_projects')
    technologies = models.CharField(max_length=500, blank=True)  # Comma-separated list of technologies
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # NEW FIELD: Connect project to module, i did this after creating the teacher app
    module = models.ForeignKey('teacher.Module', on_delete=models.SET_NULL, null=True, blank=True, 
                              related_name='projects', help_text="Module associé à ce projet")
    

    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['-created_at']

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
            'draft': 10,
            'submitted': 30,
            'in_progress': 50,
            'pending_validation': 80,
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
            # If no milestones defined, this component contributes half its weight
            progress_components['milestones'] = 20
        # Deliverables (20% weight)
        # Assume minimum 3 deliverables for a complete project
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
            progress_components['time'] = 5  # Half weight if dates not set
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
            return True  # Can't determine without end date
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
    ]
    
    recipient = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='notifications')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.recipient}: {self.message[:30]}..."
    


# Add to models.py
class ProjectActivity(models.Model):
    ACTIVITY_TYPES = [
        ('created', 'Création du projet'),
        ('status_changed', 'Changement de statut'),
        ('collaborator_added', 'Ajout de collaborateur'),
        ('collaborator_removed', 'Retrait de collaborateur'),
        ('milestone_added', 'Ajout de jalon'),
        ('milestone_completed', 'Jalon complété'),
        ('deliverable_added', 'Ajout de livrable'),
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
    author = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.author} on {self.project}"