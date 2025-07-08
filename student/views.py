from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import StudentProfile, Project
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ProjectForm, QuickPublishForm, MakeProjectPublicForm
from django.contrib import messages
from .forms import DeliverableForm
from .forms import ProjectDeliverable
from .forms import MilestoneForm
from .models import ProjectMilestone
from .models import CollaborationInvitation
from .utils import send_invitation_email
from .models import ProjectComment
from .models import ProjectActivity
from django.db.models import Q, OuterRef, Case, When
from django.utils import timezone
from .models import Notification
from .forms import StudentProfileForm, AccountSettingsForm
from .assignment_views import *
from teacher.models import DirectStudentAssignment  # Add this import at the top

# Add these stub functions for the new URL patterns
@login_required
def project_submit(request, project_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    # Allow both owners and collaborators to access the project
    project = get_object_or_404(
        Project,
        Q(student=student) | Q(collaborators=student),
        id=project_id
    )

    # Only the owner can submit
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut le soumettre.")
        return redirect('student:project_detail', project_id=project.id)

    if project.status != 'in_progress':
        messages.warning(request, "Seuls les projets en cours peuvent être soumis.")
        return redirect('student:project_detail', project_id=project.id)

    # ENHANCED: Check assignment submission requirements
    if project.is_assignment_project():
        if not project.can_be_submitted_for_assignment():
            team_status = project.get_team_size_status()
            if team_status['status'] in ['too_small', 'too_large']:
                messages.error(request, f"Impossible de soumettre: {team_status['message']}")
            elif project.is_overdue():
                messages.error(request, "Impossible de soumettre: la date limite est dépassée.")
            else:
                messages.error(request, "Le projet ne peut pas être soumis pour ce devoir.")
            return redirect('student:project_detail', project_id=project.id)

    # Change status to 'submitted'
    project.status = 'submitted'
    if project.is_assignment_project():
        project.assignment_submitted_at = timezone.now()
    project.save()

    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description="Le projet a été soumis pour évaluation"
    )

    # ENHANCED: Update assignment status if applicable
    if project.is_assignment_project():
        assignment = project.project_assignment
        if assignment.assignment_type == 'direct':
            # Update direct assignment status
            DirectStudentAssignment.objects.filter(
                assignment=assignment,
                student=student
            ).update(status='submitted')
        
        # Notify all team members for assignment projects
        team_members = project.get_team_members()
        for member in team_members:
            if member != student:  # Don't notify the submitter
                Notification.objects.create(
                    recipient=member,
                    project=project,
                    project_assignment=assignment,
                    notification_type='project_update',
                    message=f"Le projet '{project.title}' a été soumis par {student.get_full_name()}"
                )

    messages.success(request, "Votre projet a été soumis avec succès.")
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

    project.status = 'validated'
    project.save()

    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description="Projet validé"
    )

    # ENHANCED: Notify all team members for assignment projects
    if project.is_assignment_project():
        team_members = project.get_team_members()
        for member in team_members:
            Notification.objects.create(
                recipient=member,
                project=project,
                project_assignment=project.project_assignment,
                notification_type='project_update',
                message=f"Le projet '{project.title}' a été validé"
            )
        
        # Update assignment status
        if project.project_assignment.assignment_type == 'direct':
            DirectStudentAssignment.objects.filter(
                assignment=project.project_assignment,
                student__in=[member.id for member in team_members]
            ).update(status='validated')
    else:
        # Notify project owner and collaborators
        Notification.objects.create(
            recipient=project.student,
            project=project,
            notification_type='project_update',
            message=f"Votre projet '{project.title}' a été validé"
        )

        for collaborator in project.collaborators.all():
            Notification.objects.create(
                recipient=collaborator,
                project=project,
                notification_type='project_update',
                message=f"Le projet '{project.title}' a été validé"
            )

    messages.success(request, "Projet validé avec succès.")
    return redirect('student:project_detail', project_id=project.id)

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

    # ENHANCED: Notify all team members for assignment projects
    if project.is_assignment_project():
        team_members = project.get_team_members()
        for member in team_members:
            Notification.objects.create(
                recipient=member,
                project=project,
                project_assignment=project.project_assignment,
                notification_type='project_update',
                message=f"Le projet '{project.title}' a été rejeté. Veuillez consulter les commentaires et resoumettre."
            )
    else:
        # Notify project owner
        Notification.objects.create(
            recipient=project.student,
            project=project,
            notification_type='project_update',
            message=f"Votre projet '{project.title}' a été rejeté. Veuillez consulter les commentaires et resoumettre."
        )

    messages.info(request, "Projet rejeté. L'étudiant peut maintenant le modifier et resoumettre.")
    return redirect('student:project_detail', project_id=project.id)

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

# Alternative approach using get_or_create for add_collaborator in student/views.py:

@login_required
def add_collaborator(request, project_id):
    """ENHANCED: Add collaborator with full assignment constraint checking"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)

    # Only the project owner can add collaborators
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut ajouter des collaborateurs.")
        return redirect('student:project_detail', project_id=project.id)

    # Only in_progress projects can have collaborators added
    if project.status != 'in_progress':
        messages.warning(request, "Vous ne pouvez ajouter des collaborateurs qu'aux projets en cours.")
        return redirect('student:project_detail', project_id=project.id)

    # ENHANCED: Check assignment constraints
    if project.is_assignment_project():
        if not project.can_invite_more_collaborators():
            team_status = project.get_team_size_status()
            messages.error(request, f"Impossible d'ajouter des collaborateurs: {team_status['message']}")
            return redirect('student:project_detail', project_id=project.id)

    if request.method == 'POST':
        # ENHANCED: Enhanced validation for assignment projects
        if project.is_assignment_project() and not project.project_assignment.is_team_work:
            messages.error(request, "Ce devoir doit être fait individuellement - aucun collaborateur autorisé.")
            return redirect('student:project_detail', project_id=project.id)
        
        # Check if at maximum capacity (before processing invitation)
        remaining_slots = project.get_remaining_team_slots()
        if remaining_slots <= 0:
            messages.warning(request, "Votre équipe a atteint la taille maximale autorisée.")
            return redirect('student:project_detail', project_id=project.id)
            
        collaborator_id = request.POST.get('collaborator')
        if collaborator_id:
            try:
                recipient = StudentProfile.objects.get(id=collaborator_id)

                # Check if already a collaborator
                if project.collaborators.filter(id=recipient.id).exists():
                    messages.info(request, f"{recipient} est déjà un collaborateur de ce projet.")
                    return redirect('student:project_detail', project_id=project.id)

                # ENHANCED: For assignment projects, verify recipient eligibility
                if project.is_assignment_project():
                    assignment = project.project_assignment
                    
                    # Check if recipient is enrolled in the module
                    if not recipient.module_enrollments.filter(
                        module=assignment.module,
                        is_active=True
                    ).exists():
                        messages.error(request, f"{recipient} n'est pas inscrit au module {assignment.module.code}.")
                        return redirect('student:project_detail', project_id=project.id)
                    
                    # For direct assignments, check if recipient is also assigned
                    if assignment.assignment_type == 'direct':
                        if not DirectStudentAssignment.objects.filter(
                            assignment=assignment,
                            student=recipient
                        ).exists():
                            messages.error(request, f"{recipient} n'est pas assigné à ce devoir.")
                            return redirect('student:project_detail', project_id=project.id)
                    
                    # Check if recipient is already working on this assignment
                    existing_assignment_project = Project.objects.filter(
                        project_assignment=assignment
                    ).filter(
                        Q(student=recipient) | Q(collaborators=recipient)
                    ).exclude(id=project.id).first()
                    
                    if existing_assignment_project:
                        messages.error(request, f"{recipient} travaille déjà sur ce devoir dans un autre projet.")
                        return redirect('student:project_detail', project_id=project.id)

                # Use get_or_create to handle existing invitations
                invitation, created = CollaborationInvitation.objects.get_or_create(
                    project=project,
                    recipient=recipient,
                    defaults={
                        'sender': student,
                        'status': 'pending',
                        'message': ''
                    }
                )

                if created:
                    # New invitation created
                    send_invitation_email(invitation)
                    
                    # ENHANCED: Assignment-specific notification message
                    if project.is_assignment_project():
                        notification_msg = (
                            f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                            f"sur le projet '{project.title}' pour le devoir '{project.project_assignment.title}'"
                        )
                    else:
                        notification_msg = (
                            f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                            f"sur le projet '{project.title}'"
                        )
                    
                    messages.success(request, f"Invitation envoyée à {recipient}.")
                    
                    # Create notification for the recipient
                    Notification.objects.create(
                        recipient=recipient,
                        project=project,
                        project_assignment=project.project_assignment,  # Link to assignment if exists
                        notification_type='invitation',
                        message=notification_msg
                    )
                else:
                    # Invitation already exists - update it
                    if invitation.status == 'pending':
                        messages.info(request, f"Une invitation a déjà été envoyée à {recipient}.")
                    else:
                        # Reactivate the invitation
                        invitation.status = 'pending'
                        invitation.sender = student
                        invitation.message = ''
                        invitation.save()
                        
                        send_invitation_email(invitation)
                        messages.success(request, f"Nouvelle invitation envoyée à {recipient}.")
                        
                        # Create notification for the recipient
                        if project.is_assignment_project():
                            notification_msg = (
                                f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                                f"sur le projet '{project.title}' pour le devoir '{project.project_assignment.title}'"
                            )
                        else:
                            notification_msg = (
                                f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                                f"sur le projet '{project.title}'"
                            )
                        
                        Notification.objects.create(
                            recipient=recipient,
                            project=project,
                            project_assignment=project.project_assignment,
                            notification_type='invitation',
                            message=notification_msg
                        )

            except StudentProfile.DoesNotExist:
                messages.error(request, "Étudiant non trouvé.")
            except Exception as e:
                # Handle any other unexpected errors
                messages.error(request, f"Erreur lors de l'envoi de l'invitation: {str(e)}")

    return redirect('student:project_detail', project_id=project.id)

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
def notifications(request):
    """Display all notifications for the current user"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Fetch notifications and prefetch related invitations
    # Annotate each notification with the status of the relevant invitation if it exists
    notifications = Notification.objects.filter(recipient=student)
    
    notifications = notifications.annotate(
        invitation_status=Case(
            When(
                notification_type='invitation', 
                then=CollaborationInvitation.objects.filter(
                    project=OuterRef('project'), 
                    recipient=OuterRef('recipient')
                ).values('status')[:1] # Get the status of the first matching invitation
            ),
            default=None # Default for non-invitation notifications
        )
    ).order_by('-created_at')

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
            project.status = 'in_progress'
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
    """Enhanced project detail view with assignment context and team info"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Get the project with related data
    project = get_object_or_404(
        Project.objects.select_related('module', 'project_assignment', 'selected_option'),
        id=project_id,
    )

    # Check if the requesting user is either the owner or a collaborator
    is_owner = (project.student == student)
    is_collaborator = project.collaborators.filter(id=student.id).exists()

    # If the user is neither, deny access
    if not is_owner and not is_collaborator:
        messages.error(request, "Vous n'avez pas l'autorisation de voir ce projet.")
        return redirect('student:dashboard')

    # Get basic project data
    deliverables = ProjectDeliverable.objects.filter(project=project)
    milestones = ProjectMilestone.objects.filter(project=project)
    project_activities = ProjectActivity.objects.filter(project=project)
    comments = project.comments.all().select_related('author')

    # ENHANCED: Assignment-specific context
    assignment_context = {}
    if project.is_assignment_project():
        assignment = project.project_assignment
        team_info = project.get_assignment_team_info()
        
        assignment_context = {
            'assignment': assignment,
            'is_assignment_project': True,
            'assignment_type': assignment.assignment_type,
            'team_info': team_info,
            'selected_option': project.selected_option,
            'deadline_info': {
                'assignment_deadline': assignment.deadline,
                'is_overdue': project.is_overdue(),
                'can_submit': project.can_be_submitted_for_assignment(),
            }
        }
    else:
        assignment_context = {
            'is_assignment_project': False,
            'team_info': {
                'team_members': project.get_team_members(),
                'team_size': project.get_team_size(),
                'size_status': {'status': 'unlimited', 'message': 'Projet personnel', 'can_invite': True},
                'display_name': None,
            }
        }

    # For project owners, get available students for collaboration
    available_students = []
    if is_owner and project.status == 'in_progress':
        # Base query: exclude owner and current collaborators
        base_exclusions = Q(id=student.id) | Q(id__in=project.collaborators.values_list('id', flat=True))
        
        # Also exclude students who have pending invitations
        invited_student_ids = CollaborationInvitation.objects.filter(
            project=project,
            status='pending'
        ).values_list('recipient_id', flat=True)
        base_exclusions |= Q(id__in=invited_student_ids)

        if project.is_assignment_project():
            assignment = project.project_assignment
            
            # For assignment projects, only show students from the same module
            available_students = StudentProfile.objects.filter(
                module_enrollments__module=assignment.module,
                module_enrollments__is_active=True
            ).exclude(base_exclusions)
            
            # For direct assignments, further filter to only assigned students
            if assignment.assignment_type == 'direct':
                assigned_student_ids = DirectStudentAssignment.objects.filter(
                    assignment=assignment
                ).values_list('student_id', flat=True)
                available_students = available_students.filter(id__in=assigned_student_ids)
            
            # Exclude students already working on this assignment in other projects
            students_in_other_projects = Project.objects.filter(
                project_assignment=assignment
            ).exclude(id=project.id).values_list('student_id', flat=True)
            
            collaborators_in_other_projects = Project.objects.filter(
                project_assignment=assignment
            ).exclude(id=project.id).values_list('collaborators__id', flat=True)
            
            available_students = available_students.exclude(
                Q(id__in=students_in_other_projects) | Q(id__in=collaborators_in_other_projects)
            )
        else:
            # For personal projects, show all students except exclusions
            available_students = StudentProfile.objects.exclude(base_exclusions)

    # For project owners, show pending invitations
    pending_invitations = []
    if is_owner:
        pending_invitations = CollaborationInvitation.objects.filter(
            project=project,
            status='pending'
        ).select_related('recipient__user')

    # ENHANCED: Assignment-specific action buttons
    available_actions = {
        'can_edit': is_owner and project.status not in ['validated'],
        'can_delete': is_owner and project.status == 'in_progress' and not project.is_assignment_project(),
        'can_submit': is_owner and project.status == 'in_progress',
        'can_invite_collaborators': (
            is_owner and 
            project.status == 'in_progress' and 
            assignment_context.get('team_info', {}).get('size_status', {}).get('can_invite', True)
        ),
        'can_add_deliverables': (is_owner or is_collaborator) and project.status != 'validated',
        'can_add_milestones': (is_owner or is_collaborator) and project.status != 'validated',
        'can_comment': True,  # Everyone can comment
    }

    # Assignment submission validation
    if project.is_assignment_project():
        available_actions['can_submit'] = (
            is_owner and 
            project.can_be_submitted_for_assignment()
        )
        if not available_actions['can_submit'] and is_owner:
            # Provide specific reason why can't submit
            team_status = project.get_team_size_status()
            if team_status['status'] in ['too_small', 'too_large']:
                available_actions['submit_blocked_reason'] = team_status['message']
            elif not project.is_team_size_valid():
                available_actions['submit_blocked_reason'] = "Taille d'équipe invalide"
            elif project.is_overdue():
                available_actions['submit_blocked_reason'] = "Date limite dépassée"

    context = {
        'project': project,
        'deliverables': deliverables,
        'collaborators': project.collaborators.all(),
        'milestones': milestones,
        'available_students': available_students,
        'pending_invitations': pending_invitations,
        'is_owner': is_owner,
        'is_collaborator': is_collaborator,
        'project_activities': project_activities,
        'comments': comments,
        'assignment_context': assignment_context,  # ENHANCED
        'available_actions': available_actions,     # ENHANCED
    }

    return render(request, 'student/project_detail.html', context)

    










@login_required
def project_change_status(request, project_id, new_status):
    """View to change the status of a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)

    # Simplified transitions for new workflow
    allowed_transitions = {
        'in_progress': ['submitted'],
        'submitted': [],  # Only teachers can change from submitted
        'validated': [],  # Cannot change from validated
        'rejected': ['in_progress']  # Can go back to in_progress after rejection
    }

    # Check if the transition is allowed
    if new_status in allowed_transitions.get(project.status, []):
        project.status = new_status
        project.save()

        if new_status == 'submitted':
            messages.success(request, "Votre projet a été soumis pour évaluation.")
        elif new_status == 'in_progress':
            messages.success(request, "Votre projet est retourné en cours pour modifications.")

        return redirect('student:project_detail', project_id=project.id)
    else:
        messages.error(request, "Ce changement de statut n'est pas autorisé.")
        return redirect('student:project_detail', project_id=project.id)
    



@login_required
def upload_deliverable(request, project_id):
    """View to upload a deliverable file for a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, Q(id=project_id) & (Q(student=student) | Q(collaborators=student)))
    
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






# Replace the project_delete view in student/views.py with this fixed version:

@login_required
def project_delete(request, project_id):
    """View to delete a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Only allow deletion of projects that are in progress (not submitted, validated, or rejected)
    if project.status != 'in_progress':
        messages.warning(request, "Seuls les projets en cours peuvent être supprimés.")
        return redirect('student:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        # Delete any deliverables associated with this project
        ProjectDeliverable.objects.filter(project=project).delete()
        
        # Also delete any pending invitations for this project
        CollaborationInvitation.objects.filter(project=project).delete()
        
        # Delete any milestones associated with this project
        ProjectMilestone.objects.filter(project=project).delete()
        
        # Delete any comments associated with this project
        ProjectComment.objects.filter(project=project).delete()
        
        # Delete any activities associated with this project
        ProjectActivity.objects.filter(project=project).delete()
        
        # Delete any notifications associated with this project
        Notification.objects.filter(project=project).delete()
        
        # Delete the project itself
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
    if milestone.completed:
        # Undo completion
        milestone.completed = False
        milestone.completed_by = None
        milestone.completed_at = None
        milestone.save()

        messages.success(request, f"Le jalon '{milestone.title}' a été marqué comme non complété.")
    else:
        # Mark as completed
        milestone.completed = True
        milestone.completed_by = request.user
        milestone.completed_at = timezone.now()
        milestone.save()

        # Add activity
        ProjectActivity.objects.create(
            project=milestone.project,
            user=request.user,
            activity_type='milestone_completed',
            description=f"Jalon '{milestone.title}' marqué comme complété"
        )

        messages.success(request, f"Le jalon '{milestone.title}' a été marqué comme complété.")

    return redirect('student:project_detail', project_id=milestone.project.id)




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
    """ENHANCED: Accept/reject invitation with assignment constraint validation"""
    student = get_object_or_404(StudentProfile, user=request.user)
    invitation = get_object_or_404(
        CollaborationInvitation,
        id=invitation_id,
        recipient=student,
        status='pending'
    )
    
    if response == 'accept':
        # ENHANCED: Additional validation for assignment projects
        project = invitation.project
        
        if project.is_assignment_project():
            assignment = project.project_assignment
            
            # Check if recipient can still join (assignment constraints)
            if not project.can_invite_more_collaborators():
                messages.error(request, "Cette équipe a atteint sa taille maximale.")
                invitation.status = 'rejected'
                invitation.save()
                return redirect('student:invitations_list')
            
            # Check if recipient is already working on this assignment
            existing_assignment_project = Project.objects.filter(
                project_assignment=assignment
            ).filter(
                Q(student=student) | Q(collaborators=student)
            ).exclude(id=project.id).first()
            
            if existing_assignment_project:
                messages.error(request, f"Vous travaillez déjà sur ce devoir dans le projet '{existing_assignment_project.title}'.")
                invitation.status = 'rejected'
                invitation.save()
                return redirect('student:invitations_list')
            
            # Verify still enrolled in module
            if not student.module_enrollments.filter(
                module=assignment.module,
                is_active=True
            ).exists():
                messages.error(request, f"Vous n'êtes plus inscrit au module {assignment.module.code}.")
                invitation.status = 'rejected'
                invitation.save()
                return redirect('student:invitations_list')
            
            # For direct assignments, verify student is assigned
            if assignment.assignment_type == 'direct':
                if not DirectStudentAssignment.objects.filter(
                    assignment=assignment,
                    student=student
                ).exists():
                    messages.error(request, f"Vous n'êtes pas assigné à ce devoir.")
                    invitation.status = 'rejected'
                    invitation.save()
                    return redirect('student:invitations_list')
        
        # Proceed with standard acceptance using the enhanced method
        try:
            project.add_assignment_collaborator(student)
            invitation.status = 'accepted'
            invitation.save()
            
            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type='collaborator_added',
                description=f"{student.user.get_full_name() or student.user.username} a rejoint le projet en tant que collaborateur"
            )
            
            # ENHANCED: Assignment-specific success message
            if project.is_assignment_project():
                messages.success(request, 
                    f"Vous avez rejoint l'équipe pour le projet '{project.title}' "
                    f"(devoir: {project.project_assignment.title})."
                )
            else:
                messages.success(request, f"Vous êtes maintenant collaborateur sur le projet '{project.title}'.")
                
        except ValidationError as e:
            messages.error(request, str(e))
            invitation.status = 'rejected'
            invitation.save()
            
    elif response == 'reject':
        invitation.status = 'rejected'
        invitation.save()
        messages.info(request, f"Vous avez refusé l'invitation pour le projet '{invitation.project.title}'.")
    
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
    if project.status != 'in_progress':
        messages.warning(request, "Les collaborateurs ne peuvent être retirés que pour les projets en cours.")
        return redirect('student:project_detail', project_id=project.id)
    
    try:
        collaborator = StudentProfile.objects.get(id=collaborator_id)
        
        # ENHANCED: Use the assignment-aware removal method
        project.remove_assignment_collaborator(collaborator)
        messages.success(request, f"{collaborator} a été retiré des collaborateurs du projet.")
        
    except StudentProfile.DoesNotExist:
        messages.error(request, "Étudiant non trouvé.")
    except ValidationError as e:
        messages.error(request, str(e))
    
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
                author=request.user,  # Now using User directly instead of StudentProfile
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






# making projects public or private

@login_required
def make_project_public(request, project_id):
    """Student makes their project public (instant, no approval needed)"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    if not project.can_be_made_public():
        messages.error(request, "Ce projet ne peut pas être rendu public. Il doit être validé.")
        return redirect('student:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'quick_publish':
            # Quick publish with current content
            form = QuickPublishForm(request.POST)
            if form.is_valid():
                if project.make_public():
                    ProjectActivity.objects.create(
                        project=project,
                        user=request.user,
                        activity_type='made_public',
                        description="Projet rendu public"
                    )
                    messages.success(request, f"🎉 Votre projet '{project.title}' est maintenant visible publiquement!")
                    return redirect('public:project_detail', project_id=project.id)
        
        elif action == 'enhanced_publish':
            # Publish with enhanced content
            form = MakeProjectPublicForm(request.POST, request.FILES, instance=project)
            if form.is_valid():
                # Save the enhanced fields first
                enhanced_project = form.save(commit=False)
                
                # Then make it public
                if enhanced_project.make_public():
                    # Now save all the enhanced fields to the database
                    enhanced_project.save()
                    
                    # Save many-to-many relationships (tags)
                    form.save_m2m()
                    
                    ProjectActivity.objects.create(
                        project=enhanced_project,
                        user=request.user,
                        activity_type='made_public',
                        description="Projet rendu public avec contenu enrichi"
                    )
                    messages.success(request, f"🎉 Votre projet '{enhanced_project.title}' est maintenant visible publiquement!")
                    return redirect('public:project_detail', project_id=enhanced_project.id)
                else:
                    messages.error(request, "Erreur lors de la publication du projet.")
            else:
                # Form has errors, show them
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Erreur dans {field}: {error}")
    
    # GET request - show both options
    quick_form = QuickPublishForm()
    enhanced_form = MakeProjectPublicForm(instance=project)
    
    context = {
        'project': project,
        'quick_form': quick_form,
        'enhanced_form': enhanced_form,
    }
    
    return render(request, 'student/make_project_public.html', context)


@login_required
def make_project_private(request, project_id):
    """Student removes their project from public showcase"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student, is_public=True)
    
    if request.method == 'POST':
        project.make_private()
        
        ProjectActivity.objects.create(
            project=project,
            user=request.user,
            activity_type='made_private',
            description="Projet retiré de l'affichage public"
        )
        
        messages.success(request, f"Votre projet '{project.title}' n'est plus visible publiquement.")
        return redirect('student:project_detail', project_id=project.id)
    
    context = {'project': project}
    return render(request, 'student/make_project_private_confirm.html', context)





































# Add this to your existing student/views.py file (append to the end)

# Add these functions to the END of your existing student/views.py file

@login_required
def join_module(request):
    """Allow students to join a module using a code"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    if request.method == 'POST':
        module_code = request.POST.get('module_code', '').strip().upper()
        
        if not module_code:
            messages.error(request, "Veuillez entrer un code de module.")
            return redirect('student:dashboard')
        
        try:
            # Import here to avoid circular imports
            from teacher.models import Module, ModuleEnrollment
            
            module = Module.objects.get(code=module_code, is_active=True)
            
            # Check if already enrolled
            enrollment, created = ModuleEnrollment.objects.get_or_create(
                student=student,
                module=module,
                defaults={'is_active': True}
            )
            
            if created:
                messages.success(request, f"Vous avez rejoint le module '{module.name}' avec succès!")
            elif enrollment.is_active:
                messages.info(request, f"Vous êtes déjà inscrit au module '{module.name}'.")
            else:
                # Reactivate if was previously inactive
                enrollment.is_active = True
                enrollment.save()
                messages.success(request, f"Vous avez rejoint à nouveau le module '{module.name}'!")
                
        except Module.DoesNotExist:
            messages.error(request, f"Aucun module trouvé avec le code '{module_code}'. Vérifiez le code et réessayez.")
        except Exception as e:
            messages.error(request, "Une erreur est survenue. Veuillez réessayer.")
    
    return redirect('student:dashboard')

@login_required
def my_modules(request):
    """Display student's enrolled modules"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Import here to avoid circular imports
    from teacher.models import ModuleEnrollment
    
    # Get active enrollments
    enrollments = ModuleEnrollment.objects.filter(
        student=student,
        is_active=True
    ).select_related('module').prefetch_related(
        'module__assignments__teacher__user'
    ).order_by('-enrolled_at')
    
    context = {
        'student': student,
        'enrollments': enrollments,
    }
    
    return render(request, 'student/my_modules.html', context)

@login_required
def leave_module(request, module_id):
    """Allow student to leave a module"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Import here to avoid circular imports
    from teacher.models import Module, ModuleEnrollment
    
    try:
        module = Module.objects.get(id=module_id)
        enrollment = ModuleEnrollment.objects.get(
            student=student,
            module=module,
            is_active=True
        )
        
        enrollment.is_active = False
        enrollment.save()
        
        messages.success(request, f"Vous avez quitté le module '{module.name}'.")
        
    except (Module.DoesNotExist, ModuleEnrollment.DoesNotExist):
        messages.error(request, "Module non trouvé ou vous n'êtes pas inscrit à ce module.")
    
    return redirect('student:my_modules')




# the project needs confirmation before getting submitted

@login_required
def project_submit_confirmation(request, project_id):
    """Show confirmation page before project submission"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(
        Project,
        Q(student=student) | Q(collaborators=student),
        id=project_id
    )

    # Only the owner can submit
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut le soumettre.")
        return redirect('student:project_detail', project_id=project.id)

    if project.status != 'in_progress':
        messages.warning(request, "Seuls les projets en cours peuvent être soumis.")
        return redirect('student:project_detail', project_id=project.id)

    # Get pending invitations to show in confirmation
    pending_invitations = CollaborationInvitation.objects.filter(
        project=project,
        status='pending'
    ).select_related('recipient__user')

    # Get project statistics for the checklist
    deliverables_count = project.deliverables.count()
    milestones_count = project.milestones.count()
    completed_milestones_count = project.milestones.filter(completed=True).count()
    
    context = {
        'project': project,
        'pending_invitations': pending_invitations,
        'deliverables_count': deliverables_count,
        'milestones_count': milestones_count,
        'completed_milestones_count': completed_milestones_count,
        'is_ready_to_submit': True,  # You can add more complex logic here
    }
    
    return render(request, 'student/project_submit_confirmation.html', context)












# profil related views

@login_required
def profile_settings(request):
    """Main profile and settings page with tabs"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Get current tab (default to profile)
    active_tab = request.GET.get('tab', 'profile')
    
    context = {
        'student': student,
        'active_tab': active_tab,
        'profile_completion': student.get_profile_completion_percentage(),
    }
    
    return render(request, 'student/profile_settings.html', context)

@login_required
def profile_edit(request):
    """Edit student profile information"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES, instance=student, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès!")
            return redirect('student:profile_settings')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = StudentProfileForm(instance=student, user=request.user)
    
    context = {
        'student': student,
        'form': form,
        'profile_completion': student.get_profile_completion_percentage(),
    }
    
    return render(request, 'student/profile_edit.html', context)

@login_required
def profile_view(request):
    """View own profile (read-only)"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    context = {
        'student': student,
        'profile_completion': student.get_profile_completion_percentage(),
        'is_own_profile': True,
    }
    
    return render(request, 'student/profile_view.html', context)

@login_required
def account_settings(request):
    """Account settings and preferences"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    # Check if password was just changed
    password_changed = request.GET.get('changed') == 'true'
    
    if request.method == 'POST':
        form = AccountSettingsForm(request.POST)
        if form.is_valid():
            # Handle settings changes
            if form.cleaned_data.get('change_password'):
                # Redirect to password change
                return redirect('student:password_change')
            
            # Handle other settings here
            messages.success(request, "Paramètres mis à jour avec succès!")
            return redirect('student:profile_settings')
    else:
        form = AccountSettingsForm()
    
    if password_changed:
        messages.success(request, "🎉 Votre mot de passe a été modifié avec succès!")
    
    context = {
        'student': student,
        'form': form,
        'password_changed': password_changed,
    }
    
    return render(request, 'student/account_settings.html', context)

@login_required
def delete_profile_picture(request):
    """Delete profile picture (AJAX endpoint)"""
    if request.method == 'POST':
        student = get_object_or_404(StudentProfile, user=request.user)
        
        if student.profile_picture:
            # Delete the file
            student.profile_picture.delete()
            messages.success(request, "Photo de profil supprimée avec succès.")
        else:
            messages.warning(request, "Aucune photo de profil à supprimer.")
        
        return redirect('student:profile_edit')
    
    return redirect('student:profile_settings')