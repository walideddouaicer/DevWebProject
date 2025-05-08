from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import StudentProfile, Project
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ProjectForm
from django.contrib import messages
from .forms import DeliverableForm
from .forms import ProjectDeliverable

@login_required
def dashboard(request):
    """Student dashboard view with search and filtering"""
    try:
        student = get_object_or_404(StudentProfile, user=request.user)
        
        # Get filter parameters
        search_query = request.GET.get('search', '')
        project_type = request.GET.get('type', '')
        status = request.GET.get('status', '')
        
        # Start with all projects for this student
        all_projects = Project.objects.filter(student=student)
        
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
        
        # Get active projects for display
        active_projects = all_projects.filter(
            status__in=['draft', 'submitted', 'in_progress', 'pending_validation']
        )
        
        # Get project type choices for the filter dropdown
        project_type_choices = dict(Project.PROJECT_TYPES)
        status_choices = dict(Project.STATUS_CHOICES)
        
        context = {
            'student': student,
            'total_projects': total_projects,
            'completed_projects': completed_projects,
            'in_progress_projects': in_progress_projects,
            'pending_validation': pending_validation,
            'active_projects': active_projects,
            'search_query': search_query,
            'project_type': project_type,
            'status': status,
            'project_type_choices': project_type_choices,
            'status_choices': status_choices,
        }
        
        return render(request, 'student/dashboard.html', context)
    except StudentProfile.DoesNotExist:
        # Handle case where profile doesn't exist
        context = {'error': 'Student profile not found'}
        return render(request, 'student/dashboard.html', context)
    




@login_required
def project_create(request):
    """View to create a new project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.student = student
            project.status = 'draft'  # Set initial status
            project.save()
            
            # Redirect to the dashboard or project detail page
            return redirect('dashboard')
    else:
        form = ProjectForm()
    
    context = {
        'form': form,
        'title': 'Créer un nouveau projet'
    }
    
    return render(request, 'student/project_form.html', context)






@login_required
def project_detail(request, project_id):
    """View to display detailed information about a specific project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    
    deliverables = ProjectDeliverable.objects.filter(project=project)
    
    context = {
        'project': project,
        'deliverables': deliverables,
    }
    
    return render(request, 'student/project_detail.html', context)







@login_required
def project_edit(request, project_id):
    """View to edit an existing project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Don't allow editing if the project is already validated
    if project.status == 'validated':
        messages.warning(request, "Les projets validés ne peuvent plus être modifiés.")
        return redirect('project_detail', project_id=project.id)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Le projet a été mis à jour avec succès.")
            return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project)
    
    context = {
        'form': form,
        'project': project,
        'title': 'Modifier le projet'
    }
    
    return render(request, 'student/project_form.html', context)


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
        
        return redirect('project_detail', project_id=project.id)
    else:
        messages.error(request, "Ce changement de statut n'est pas autorisé.")
        return redirect('project_detail', project_id=project.id)
    



@login_required
def upload_deliverable(request, project_id):
    """View to upload a deliverable file for a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)
    
    # Don't allow uploads for validated projects
    if project.status == 'validated':
        messages.warning(request, "Impossible d'ajouter des livrables à un projet validé.")
        return redirect('project_detail', project_id=project.id)
    
    if request.method == 'POST':
        form = DeliverableForm(request.POST, request.FILES)
        if form.is_valid():
            deliverable = form.save(commit=False)
            deliverable.project = project
            deliverable.save()
            
            messages.success(request, "Le livrable a été ajouté avec succès.")
            return redirect('project_detail', project_id=project.id)
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
        return redirect('project_detail', project_id=project.id)
    
    if request.method == 'POST':
        # Delete any deliverables associated with this project
        ProjectDeliverable.objects.filter(project=project).delete()
        
        # Delete the project
        project.delete()
        
        messages.success(request, "Le projet a été supprimé avec succès.")
        return redirect('dashboard')
    
    context = {
        'project': project,
    }
    
    return render(request, 'student/project_delete_confirm.html', context)