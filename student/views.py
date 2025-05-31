from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import StudentProfile, Project
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ProjectForm
from django.contrib import messages
from .forms import DeliverableForm
from .forms import ProjectDeliverable
from .forms import MilestoneForm
from .models import ProjectMilestone
from .models import CollaborationInvitation
from .utils import send_invitation_email
from .models import ProjectComment
from .models import ProjectActivity
from django.db.models import Q
from django.utils import timezone
from .models import Notification

# Add these stub functions for the new URL patterns
@login_required
def project_submit(request, project_id):
    # Implementation will be added later
    return redirect('student:project_detail', project_id=project_id)

@login_required
def project_approve(request, project_id):
    # Implementation will be added later
    return redirect('student:project_detail', project_id=project_id)

@login_required
def project_reject(request, project_id):
    # Implementation will be added later
    return redirect('student:project_detail', project_id=project_id)

@login_required
def complete_milestone(request, milestone_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    milestone = get_object_or_404(
        ProjectMilestone,
        id=milestone_id,
        project__in=Project.objects.filter(
            Q(student=student) | Q(collaborators=student)
        )
    )
    
    # Only mark as completed if it's not already completed
    if not milestone.completed:
        milestone.completed = True
        milestone.save()
        
        # Record activity
        ProjectActivity.objects.create(
            project=milestone.project,
            user=request.user,
            activity_type='milestone_completed',
            description=f"Jalon '{milestone.title}' marqué comme complété"
        )
        
        messages.success(request, f"Le jalon '{milestone.title}' a été marqué comme complété.")
    
    return redirect('student:project_detail', project_id=milestone.project.id)

@login_required
def add_collaborator(request, project_id):
    # Implementation will be added later
    return redirect('student:project_detail', project_id=project_id)

@login_required
def add_feedback(request, project_id):
    """Allow teachers to add feedback to projects"""
    if not request.user.is_staff:
        messages.error(request, "Seuls les enseignants peuvent ajouter des commentaires.")
        return redirect('student:project_detail', project_id=project_id)
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            # Check if teacher has a StudentProfile (they might not)
            try:
                author = StudentProfile.objects.get(user=request.user)
            except StudentProfile.DoesNotExist:
                # Create a temporary profile for the teacher or handle differently
                messages.error(request, "Profil enseignant non trouvé. Contactez l'administrateur.")
                return redirect('student:project_detail', project_id=project_id)
            # Create a special comment marked as feedback
            comment = ProjectComment(
                project=project,
                author=author,
                content=f"[FEEDBACK ENSEIGNANT]\n{content}"
            )
            comment.save()
            # Create notification for project owner
            Notification.objects.create(
                recipient=project.student,
                project=project,
                notification_type='project_update',
                message=f"Nouveau feedback de {request.user.get_full_name()} sur votre projet"
            )
            messages.success(request, "Feedback ajouté avec succès.")
        else:
            messages.error(request, "Le feedback ne peut pas être vide.")
    return redirect('student:project_detail', project_id=project.id)

@login_required
def project_approve(request, project_id):
    """Teacher approves a submitted project"""
    if not request.user.is_staff:
        messages.error(request, "Seuls les enseignants peuvent approuver les projets.")
        return redirect('student:project_detail', project_id=project_id)
    project = get_object_or_404(Project, id=project_id)
    if project.status != 'submitted':
        messages.warning(request, "Seuls les projets soumis peuvent être approuvés.")
        return redirect('student:project_detail', project_id=project_id)
    project.status = 'in_progress'
    project.save()
    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description="Projet approuvé et passé en cours"
    )
    # Notify student
    Notification.objects.create(
        recipient=project.student,
        project=project,
        notification_type='project_update',
        message="Votre projet a été approuvé et est maintenant en cours"
    )
    messages.success(request, "Projet approuvé avec succès.")
    return redirect('student:project_detail', project_id=project_id)

@login_required
def project_reject(request, project_id):
    """Teacher rejects a submitted project"""
    if not request.user.is_staff:
        messages.error(request, "Seuls les enseignants peuvent rejeter les projets.")
        return redirect('student:project_detail', project_id=project_id)
    project = get_object_or_404(Project, id=project_id)
    if project.status != 'submitted':
        messages.warning(request, "Seuls les projets soumis peuvent être rejetés.")
        return redirect('student:project_detail', project_id=project_id)
    project.status = 'rejected'
    project.save()
    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description="Projet rejeté - révisions nécessaires"
    )
    # Notify student
    Notification.objects.create(
        recipient=project.student,
        project=project,
        notification_type='project_update',
        message="Votre projet a été rejeté. Veuillez consulter les commentaires et resoumettre."
    )
    messages.info(request, "Projet rejeté. L'étudiant peut maintenant le modifier et resoumettre.")
    return redirect('student:project_detail', project_id=project_id)

@login_required
def notifications(request):
    """Display all notifications for the current user"""
    student = get_object_or_404(StudentProfile, user=request.user)
    notifications = Notification.objects.filter(recipient=student).order_by('-created_at')
    context = {
        'notifications': notifications,
    }
    return render(request, 'student/notifications.html', context)

@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    student = get_object_or_404(StudentProfile, user=request.user)
    notification = get_object_or_404(Notification, id=notification_id, recipient=student)
    notification.is_read = True
    notification.save()
    return redirect('student:notifications')

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    student = get_object_or_404(StudentProfile, user=request.user)
    Notification.objects.filter(recipient=student, is_read=False).update(is_read=True)
    messages.success(request, "Toutes les notifications ont été marquées comme lues.")
    return redirect('student:notifications')

# Updated dashboard view
@login_required
def dashboard(request):
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    project_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    view = request.GET.get('view', 'all')  # 'all', 'mine', 'collaborated'
    
    # Start with all projects for this student
    if view == 'mine':
        all_projects = Project.objects.filter(student=student)
    elif view == 'collaborated':
        all_projects = Project.objects.filter(collaborators=student)
    else:  # 'all' - default
        all_projects = Project.objects.filter(
            Q(student=student) | Q(collaborators=student)
        ).distinct()
    
    # Apply filters if provided
    if search_query:
        all_projects = all_projects.filter(title__icontains=search_query)
    
    if project_type:
        all_projects = all_projects.filter(project_type=project_type)
        
    if status:
        all_projects = all_projects.filter(status=status)
    
    # Get project statistics
    total_projects = all_projects.count()
    completed_projects = all_projects.filter(status='validated').count()
    in_progress_projects = all_projects.filter(status='in_progress').count()
    pending_validation = all_projects.filter(status='pending_validation').count()
    
    # Get pending invitations count
    pending_invitations_count = CollaborationInvitation.objects.filter(
        recipient=student,
        status='pending'
    ).count()
    
    # Get active projects for display, applying the same filters
    # Base queries for owned and collaborated projects
    owned_projects_base = Project.objects.filter(student=student)
    collaborated_projects_base = Project.objects.filter(collaborators=student).exclude(student=student)
    
    # Apply the same filters to both collections
    if search_query:
        owned_projects_base = owned_projects_base.filter(title__icontains=search_query)
        collaborated_projects_base = collaborated_projects_base.filter(title__icontains=search_query)
    
    if project_type:
        owned_projects_base = owned_projects_base.filter(project_type=project_type)
        collaborated_projects_base = collaborated_projects_base.filter(project_type=project_type)
    
    if status:
        owned_projects_base = owned_projects_base.filter(status=status)
        collaborated_projects_base = collaborated_projects_base.filter(status=status)
        
    # Assign the filtered projects
    owned_projects = owned_projects_base
    collaborated_projects = collaborated_projects_base
    
    # Get project type choices for the filter dropdown
    project_type_choices = dict(Project.PROJECT_TYPES)
    status_choices = dict(Project.STATUS_CHOICES)
    
    context = {
        'student': student,
        'total_projects': total_projects,
        'completed_projects': completed_projects,
        'in_progress_projects': in_progress_projects,
        'pending_validation': pending_validation,
        'pending_invitations_count': pending_invitations_count,
        'owned_projects': owned_projects,
        'collaborated_projects': collaborated_projects,
        'search_query': search_query,
        'project_type': project_type,
        'status': status,
        'project_type_choices': project_type_choices,
        'status_choices': status_choices,
        'view': view,
    }
    
    return render(request, 'student/dashboard.html', context)
    




@login_required
def project_create(request):
    student = get_object_or_404(StudentProfile, user=request.user)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, current_student=student)
        if form.is_valid():
            project = form.save(commit=False)
            project.student = student
            project.status = 'draft'
            project.save()
            
            # This is needed to save many-to-many relationships
            form.save_m2m()
            
            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type='created',
                description="Projet créé"
            )
            
            messages.success(request, "Projet créé avec succès.")
            return redirect('student:project_detail', project_id=project.id)
    else:
        form = ProjectForm(current_student=student)
    
    context = {
        'form': form,
        'title': 'Créer un nouveau projet'
    }
    
    return render(request, 'student/project_form.html', context)

@login_required
def project_edit(request, project_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    #dont allow editing if the project is already validated
    if project.status == 'validated':
        messages.warning(request, "Les projets validés ne peuvent plus être modifiés.")
        return redirect('student:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project, current_student=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Projet mis à jour avec succès.")
            return redirect('student:project_detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project, current_student=student)
    
    context = {
        'form': form,
        'project': project,
        'title': 'Modifier le projet'
    }
    
    return render(request, 'student/project_form.html', context)






@login_required
def project_detail(request, project_id):
    """View to display detailed information about a specific project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    # Allow both project owners and collaborators to view the project
    project = get_object_or_404(
        Project, 
        Q(student=student) | Q(collaborators=student),
        id=project_id,
    )

    
    # Check if user is owner or collaborator
    is_owner = (project.student == student)
    is_collaborator = project.collaborators.filter(id=student.id).exists()
    
    deliverables = ProjectDeliverable.objects.filter(project=project)
    collaborators = project.collaborators.all()
    milestones = ProjectMilestone.objects.filter(project=project)
    
    # Get project activities
    project_activities = ProjectActivity.objects.filter(project=project)
    
    # For project owners, get available students for collaboration
    available_students = []
    if is_owner and project.status == 'draft':
        # Get students who are not already collaborators and not the owner
        available_students = StudentProfile.objects.exclude(
            Q(id=student.id) | 
            Q(id__in=project.collaborators.values_list('id', flat=True))
        )
    
    # For project owners, show pending invitations
    pending_invitations = []
    if is_owner:
        pending_invitations = CollaborationInvitation.objects.filter(
            project=project,
            status='pending'
        )
    
    context = {
        'project': project,
        'deliverables': deliverables,
        'collaborators': collaborators,
        'milestones': milestones,
        'available_students': available_students,
        'pending_invitations': pending_invitations,
        'is_owner': is_owner,
        'is_collaborator': is_collaborator,
        'project_activities': project_activities,
    }
    
    return render(request, 'student/project_detail.html', context)

    










@login_required
def project_change_status(request, project_id, new_status):
    """View to change the status of a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Define allowed status transitions
    allowed_transitions = {
        'draft': ['submitted'],
        'submitted': [],  # Only teachers can change from submitted
        'in_progress': [],  # Only teachers can change from in_progress
        'pending_validation': [],  # Only teachers can change from pending_validation
        'validated': [],  # Cannot change from validated
        'rejected': ['draft']  # Can resubmit after rejection
    }
    
    # Check if the transition is allowed
    if new_status in allowed_transitions.get(project.status, []):
        project.status = new_status
        project.save()
        
        if new_status == 'submitted':
            messages.success(request, "Votre projet a été soumis pour évaluation.")
        elif new_status == 'draft':
            messages.success(request, "Votre projet est retourné à l'état brouillon.")
        
        return redirect('student:project_detail', project_id=project.id)
    else:
        messages.error(request, "Ce changement de statut n'est pas autorisé.")
        return redirect('student:project_detail', project_id=project.id)
    



@login_required
def upload_deliverable(request, project_id):
    """View to upload a deliverable file for a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Don't allow uploads for validated projects
    if project.status == 'validated':
        messages.warning(request, "Impossible d'ajouter des livrables à un projet validé.")
        return redirect('student:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        form = DeliverableForm(request.POST, request.FILES)
        if form.is_valid():
            deliverable = form.save(commit=False)
            deliverable.project = project
            deliverable.save()
            
            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type='deliverable_added',
                description=f"Livrable ajouté: {deliverable.name}"
            )
            
            messages.success(request, "Le livrable a été ajouté avec succès.")
            return redirect('student:project_detail', project_id=project.id)
    else:
        form = DeliverableForm()
    
    context = {
        'form': form,
        'project': project,
        'title': 'Ajouter un livrable'
    }
    
    return render(request, 'student/upload_deliverable.html', context)






@login_required
def project_delete(request, project_id):
    """View to delete a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Don't allow deletion of projects that are not in draft status
    if project.status != 'draft':
        messages.warning(request, "Seuls les projets en brouillon peuvent être supprimés.")
        return redirect('student:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        # Delete any deliverables associated with this project
        ProjectDeliverable.objects.filter(project=project).delete()
        
        # Delete the project
        project.delete()
        
        messages.success(request, "Le projet a été supprimé avec succès.")
        return redirect('student:dashboard')
    
    context = {
        'project': project,
    }
    
    return render(request, 'student/project_delete_confirm.html', context)





@login_required
def add_milestone(request, project_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(
        Project, 
        Q(student=student) | Q(collaborators=student),
        id=project_id,
    )
    
    if request.method == 'POST':
        form = MilestoneForm(request.POST)
        if form.is_valid():
            milestone = form.save(commit=False)
            milestone.project = project
            milestone.save()
            
            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type='milestone_added',
                description=f"Jalon ajouté: {milestone.title}"
            )
            
            messages.success(request, "Jalon ajouté avec succès.")
            return redirect('student:project_detail', project_id=project.id)
    else:
        form = MilestoneForm()
    
    context = {
        'form': form,
        'project': project,
        'title': 'Ajouter un jalon'
    }
    
    return render(request, 'student/milestone_form.html', context)

@login_required
def toggle_milestone(request, milestone_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    milestone = get_object_or_404(
        ProjectMilestone,
        id=milestone_id,
        project__in=Project.objects.filter(
            Q(student=student) | Q(collaborators=student)
        )
    )
    
    # Toggle completed status
    old_status = milestone.completed
    milestone.completed = not milestone.completed
    milestone.save()
    
    # Add activity only when marking as completed
    if milestone.completed and not old_status:
        ProjectActivity.objects.create(
            project=milestone.project,
            user=request.user,
            activity_type='milestone_completed',
            description=f"Jalon '{milestone.title}' marqué comme complété"
        )
    
    return redirect('student:project_detail', project_id=milestone.project.id)




@login_required
def add_collaborator(request, project_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Only the project owner can add collaborators
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut ajouter des collaborateurs.")
        return redirect('student:project_detail', project_id=project.id)
    
    # Only draft projects can have collaborators added or modified
    if project.status != 'draft':
        messages.warning(request, "Vous ne pouvez ajouter des collaborateurs qu'aux projets en état brouillon.")
        return redirect('student:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        collaborator_id = request.POST.get('collaborator')
        if collaborator_id:
            try:
                recipient = StudentProfile.objects.get(id=collaborator_id)
                
                # Check if already a collaborator
                if project.collaborators.filter(id=recipient.id).exists():
                    messages.info(request, f"{recipient} est déjà un collaborateur de ce projet.")
                    return redirect('student:project_detail', project_id=project.id)
                
                # Check for existing invitations
                existing_invitation = CollaborationInvitation.objects.filter(
                    project=project,
                    recipient=recipient,
                    status='pending'
                ).first()
                
                if existing_invitation:
                    messages.info(request, f"Une invitation a déjà été envoyée à {recipient}.")
                else:
                    # Create new invitation
                    invitation = CollaborationInvitation(
                        project=project,
                        sender=student,
                        recipient=recipient
                    )
                    invitation.save()
                    send_invitation_email(invitation)
                    messages.success(request, f"Invitation envoyée à {recipient}.")
                    
                    # Here you could add email notification logic
                    
            except StudentProfile.DoesNotExist:
                messages.error(request, "Étudiant non trouvé.")
        
    return redirect('student:project_detail', project_id=project.id)



#view and respond to invitation
@login_required
def invitations_list(request):
    """View to display pending collaboration invitations"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Get received invitations
    received_invitations = CollaborationInvitation.objects.filter(
        recipient=student,
        status='pending'
    )
    
    # Get sent invitations
    sent_invitations = CollaborationInvitation.objects.filter(
        sender=student,
        status='pending'
    )
    
    context = {
        'received_invitations': received_invitations,
        'sent_invitations': sent_invitations,
    }
    
    return render(request, 'student/invitations_list.html', context)

@login_required
def respond_to_invitation(request, invitation_id, response):
    """View to accept or reject a collaboration invitation"""
    student = get_object_or_404(StudentProfile, user=request.user)
    invitation = get_object_or_404(
        CollaborationInvitation,
        id=invitation_id,
        recipient=student,
        status='pending'
    )
    
    if response == 'accept':
        # Add student as collaborator
        invitation.project.collaborators.add(student)
        invitation.status = 'accepted'
        invitation.save()
        
        # Record activity
        ProjectActivity.objects.create(
            project=invitation.project,
            user=request.user,
            activity_type='collaborator_added',
            description=f"{student.user.get_full_name() or student.user.username} a rejoint le projet en tant que collaborateur"
        )
        
        messages.success(request, f"Vous êtes maintenant collaborateur sur le projet {invitation.project.title}.")
    elif response == 'reject':
        invitation.status = 'rejected'
        invitation.save()
        messages.info(request, f"Vous avez refusé l'invitation pour le projet {invitation.project.title}.")
    
    return redirect('student:invitations_list')





# removing a collaborator
@login_required
def remove_collaborator(request, project_id, collaborator_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Only project owner can remove collaborators
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut retirer des collaborateurs.")
        return redirect('student:project_detail', project_id=project.id)
    
    # Verify the project is in draft status
    if project.status != 'draft':
        messages.warning(request, "Les collaborateurs ne peuvent être retirés que pour les projets en état brouillon.")
        return redirect('student:project_detail', project_id=project.id)
    
    try:
        collaborator = StudentProfile.objects.get(id=collaborator_id)
        if project.collaborators.filter(id=collaborator.id).exists():
            project.collaborators.remove(collaborator)
            messages.success(request, f"{collaborator} a été retiré des collaborateurs du projet.")
        else:
            messages.warning(request, "Cet étudiant n'est pas un collaborateur du projet.")
    except StudentProfile.DoesNotExist:
        messages.error(request, "Étudiant non trouvé.")
    
    return redirect('student:project_detail', project_id=project.id)






# cancel invitation
@login_required
def cancel_invitation(request, invitation_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    invitation = get_object_or_404(
        CollaborationInvitation,
        id=invitation_id,
        sender=student,
        status='pending'
    )
    
    project_id = invitation.project.id
    recipient_name = invitation.recipient
    
    # Delete the invitation
    invitation.delete()
    
    messages.success(request, f"L'invitation envoyée à {recipient_name} a été annulée.")
    return redirect('student:project_detail', project_id=project_id)




@login_required
def add_comment(request, project_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(
        Project, 
        Q(student=student) | Q(collaborators=student),
        id=project_id
    )
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment = ProjectComment(
                project=project,
                author=student,
                content=content
            )
            comment.save()
            
            # Add activity record
            activity = ProjectActivity(
                project=project,
                user=request.user,
                activity_type='comment_added',
                description=f"A ajouté un commentaire: \"{content[:50]}{'...' if len(content) > 50 else ''}\""
            )
            activity.save()
            
            messages.success(request, "Commentaire ajouté avec succès.")
        else:
            messages.error(request, "Le commentaire ne peut pas être vide.")
    
    return redirect('student:project_detail', project_id=project.id)




@login_required
def project_submit(request, project_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    if project.status != 'draft':
        messages.warning(request, "Seuls les projets en brouillon peuvent être soumis.")
        return redirect('student:project_detail', project_id=project.id)
    
    # Change status to 'submitted'
    project.status = 'submitted'
    project.save()
    
    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description="Le projet a été soumis pour évaluation"
    )
    
    messages.success(request, "Votre projet a été soumis avec succès.")
    return redirect('student:project_detail', project_id=project.id)