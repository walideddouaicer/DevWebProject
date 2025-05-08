from django.db import models
from django.contrib.auth.models import User
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
        ('draft', 'Brouillon'),
        ('submitted', 'Soumis'),
        ('in_progress', 'En cours'),
        ('completed', 'Complété'),
        ('pending_validation', 'En attente de validation'),
        ('validated', 'Validé'),
        ('rejected', 'Rejeté'),
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
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
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
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