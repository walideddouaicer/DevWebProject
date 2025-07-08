# student/assignment_views.py - FINAL CLEAN VERSION with pure collaboration logic

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import ValidationError
from functools import wraps
from django.urls import reverse

from .models import StudentProfile, Project, ProjectActivity, Notification, CollaborationInvitation
from teacher.models import (
    ProjectAssignment, ProjectOption, 
    DirectStudentAssignment, Module
)
from .forms import ProjectForm

# Helper functions

def get_student_or_error(request):
    """Helper function to get student profile with consistent error handling"""
    try:
        return StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        messages.error(request, "Profil étudiant non trouvé.")
        return None

def check_module_access(student, assignment):
    """Helper function to check if student has access to assignment's module"""
    return assignment.module.enrollments.filter(
        student=student,
        is_active=True
    ).exists()

def requires_module_access(view_func):
    """Decorator to ensure student has access to assignment's module"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        student = get_student_or_error(request)
        if not student:
            return redirect('login')
        
        # Extract assignment_id from kwargs
        assignment_id = kwargs.get('assignment_id')
        
        if assignment_id:
            assignment = get_object_or_404(ProjectAssignment, id=assignment_id)
            
            # Check module access
            if not check_module_access(student, assignment):
                messages.error(request, "Vous n'avez pas accès à ce devoir.")
                return redirect('student:assignments_dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
def assignments_dashboard(request):
    """Enhanced assignments dashboard with direct project creation links"""
    student = get_student_or_error(request)
    if not student:
        return redirect('login')
    
    # Get student's modules with optimized query
    enrolled_module_ids = list(student.module_enrollments.filter(
        is_active=True
    ).values_list('module_id', flat=True))
    
    if not enrolled_module_ids:
        context = {
            'student': student,
            'direct_assignments': [],
            'choice_assignments': [],
            'team_assignments': [],
            'pending_invitations': [],
            'total_assignments': 0,
            'completed_assignments': 0,
            'pending_assignments': 0,
            'overdue_assignments': 0,
        }
        return render(request, 'student/assignments/dashboard.html', context)
    
    # Get all assignments with optimized prefetching
    all_assignments = ProjectAssignment.objects.filter(
        module_id__in=enrolled_module_ids,
        status__in=['published', 'in_progress']
    ).select_related(
        'module', 'teacher__user'
    ).prefetch_related(
        'project_options',
        'direct_assignments__student',
        'submitted_projects'
    ).order_by('-created_at')
    
    # Get student's existing assignment projects
    student_assignment_projects = {}
    for project in Project.objects.filter(
        Q(student=student) | Q(collaborators=student),
        project_assignment__in=all_assignments
    ).select_related('project_assignment', 'selected_option'):
        student_assignment_projects[project.project_assignment.id] = project
    
    # Get student's direct assignments
    student_direct_assignments = {
        da.assignment_id: da for da in DirectStudentAssignment.objects.filter(
            assignment__in=all_assignments,
            student=student
        ).select_related('assignment')
    }
    
    # Process assignments efficiently
    direct_assignments = []
    choice_assignments = []
    team_assignments = []
    
    for assignment in all_assignments:
        assignment_data = {
            'assignment': assignment,
            'status': None,
            'project': None,
            'can_create_project': False,
            'is_overdue': False,
            'action_needed': None,
            'team_info': None,
        }
        
        # Check if student has a project for this assignment
        existing_project = student_assignment_projects.get(assignment.id)
        if existing_project:
            assignment_data['project'] = existing_project
            assignment_data['status'] = 'has_project'
            assignment_data['team_info'] = {
                'size': existing_project.get_team_size(),
                'members_display': existing_project.get_assignment_team_display(),
                'can_submit': existing_project.can_be_submitted_for_assignment(),
                'size_status': existing_project.get_team_size_status(),
            }
        else:
            # No project yet - check if can create
            can_create, reason = can_student_create_assignment_project(student, assignment)
            assignment_data['can_create_project'] = can_create
            if not can_create:
                assignment_data['status'] = 'blocked'
                assignment_data['action_needed'] = reason
            else:
                assignment_data['status'] = 'ready_to_start'
                if assignment.assignment_type == 'choice_based':
                    assignment_data['action_needed'] = 'Sélectionner un projet'
                else:
                    assignment_data['action_needed'] = 'Créer le projet'
        
        # Check for overdue status
        if assignment.assignment_type == 'direct':
            direct_assignment = student_direct_assignments.get(assignment.id)
            if direct_assignment:
                assignment_data['is_overdue'] = direct_assignment.is_overdue()
                if not existing_project:
                    assignment_data['status'] = 'assigned'
                direct_assignments.append(assignment_data)
        else:  # choice_based
            # Check various deadlines for overdue status
            now = timezone.now()
            if assignment.selection_deadline and now > assignment.selection_deadline and not existing_project:
                assignment_data['is_overdue'] = True
                assignment_data['status'] = 'missed_deadline'
                assignment_data['action_needed'] = 'Période de sélection terminée'
            elif assignment.deadline and now > assignment.deadline:
                assignment_data['is_overdue'] = True
            
            if assignment.is_team_work:
                team_assignments.append(assignment_data)
            else:
                choice_assignments.append(assignment_data)
    
    # Get pending collaboration invitations
    pending_invitations = CollaborationInvitation.objects.filter(
        recipient=student,
        status='pending'
    ).select_related(
        'project__project_assignment', 'sender__user'
    ).order_by('-created_at')
    
    # Calculate statistics
    all_assignment_data = direct_assignments + choice_assignments + team_assignments
    total_assignments = len(all_assignment_data)
    completed_assignments = sum(1 for a in all_assignment_data 
                              if a['project'] and a['project'].status == 'validated')
    pending_assignments = sum(1 for a in all_assignment_data 
                            if a['status'] in ['assigned', 'ready_to_start'] and not a['project'])
    overdue_assignments = sum(1 for a in all_assignment_data if a['is_overdue'])
    
    context = {
        'student': student,
        'direct_assignments': direct_assignments,
        'choice_assignments': choice_assignments,
        'team_assignments': team_assignments,
        'pending_invitations': pending_invitations,
        'total_assignments': total_assignments,
        'completed_assignments': completed_assignments,
        'pending_assignments': pending_assignments,
        'overdue_assignments': overdue_assignments,
    }
    
    return render(request, 'student/assignments/dashboard.html', context)


@requires_module_access
def assignment_detail(request, assignment_id):
    """View detailed information about an assignment"""
    student = get_student_or_error(request)
    if not student:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment.objects.select_related('module', 'teacher__user'),
        id=assignment_id,
        module__enrollments__student=student,
        module__enrollments__is_active=True,
        status__in=['published', 'in_progress']
    )
    
    # Get student's involvement in this assignment
    assignment_data = {
        'assignment': assignment,
        'student_status': None,
        'direct_assignment': None,
        'project': None,
        'can_create_project': False,
        'available_options': [],
    }
    
    if assignment.assignment_type == 'direct':
        # Check direct assignment
        try:
            direct_assignment = DirectStudentAssignment.objects.get(
                assignment=assignment,
                student=student
            )
            assignment_data['direct_assignment'] = direct_assignment
            assignment_data['student_status'] = direct_assignment.status
        except DirectStudentAssignment.DoesNotExist:
            assignment_data['student_status'] = 'not_assigned'
    
    else:  # choice_based
        assignment_data['student_status'] = 'can_create_project'
        
        # Get available options if can create project
        can_create, reason = can_student_create_assignment_project(student, assignment)
        assignment_data['can_create_project'] = can_create
        
        if can_create:
            # Get available options
            available_options = []
            for option in assignment.project_options.filter(is_available=True):
                if option.is_selectable():
                    available_options.append(option)
            assignment_data['available_options'] = available_options
    
    # Check for existing project
    existing_project = Project.objects.filter(
        Q(student=student) | Q(collaborators=student),
        project_assignment=assignment
    ).first()
    
    if existing_project:
        assignment_data['project'] = existing_project
        assignment_data['student_status'] = 'has_project'
    
    # Get project options for choice-based assignments
    project_options = []
    if assignment.assignment_type == 'choice_based':
        project_options = assignment.project_options.filter(is_available=True).order_by('order')
    
    context = {
        'student': student,
        'assignment_data': assignment_data,
        'project_options': project_options,
    }
    
    return render(request, 'student/assignments/detail.html', context)


@login_required
@transaction.atomic
def create_assignment_project_direct(request, assignment_id):
    """Create project directly from assignment - NEW SIMPLIFIED VERSION"""
    student = get_student_or_error(request)
    if not student:
        return redirect('login')
    
    # Get assignment and verify access
    assignment = get_object_or_404(
        ProjectAssignment.objects.select_related('module'),
        id=assignment_id,
        module__enrollments__student=student,
        module__enrollments__is_active=True,
        status__in=['published', 'in_progress']
    )
    
    # Check if student can create project for this assignment
    can_create, reason = can_student_create_assignment_project(student, assignment)
    if not can_create:
        messages.error(request, reason)
        return redirect('student:assignment_detail', assignment_id=assignment.id)
    
    # Check if project already exists
    existing_project = get_existing_assignment_project(student, assignment)
    if existing_project:
        messages.info(request, "Un projet existe déjà pour ce devoir.")
        return redirect('student:project_detail', project_id=existing_project.id)
    
    # Handle different assignment types
    if assignment.assignment_type == 'choice_based':
        return handle_choice_based_assignment_project(request, student, assignment)
    else:  # direct assignment
        return handle_direct_assignment_project(request, student, assignment)


def can_student_create_assignment_project(student, assignment):
    """Check if student can create a project for this assignment"""
    
    # Check assignment status
    if assignment.status != 'published':
        return False, "Ce devoir n'est pas encore disponible."
    
    # Check deadlines
    now = timezone.now()
    if assignment.deadline and now > assignment.deadline:
        return False, "La date limite pour ce devoir est dépassée."
    
    # For direct assignments, check if student is assigned
    if assignment.assignment_type == 'direct':
        try:
            direct_assignment = DirectStudentAssignment.objects.get(
                assignment=assignment,
                student=student
            )
            if not direct_assignment.can_start_project():
                return False, "Vous ne pouvez pas encore commencer ce projet."
        except DirectStudentAssignment.DoesNotExist:
            return False, "Vous n'êtes pas assigné à ce devoir."
    
    # For choice-based assignments, check if in valid timeframe
    if assignment.assignment_type == 'choice_based':
        if assignment.selection_deadline and now > assignment.selection_deadline:
            return False, "La période de sélection des projets est terminée."
    
    return True, ""


def get_existing_assignment_project(student, assignment):
    """Check if student already has a project for this assignment"""
    
    # Check as project owner or collaborator
    existing = Project.objects.filter(
        Q(student=student) | Q(collaborators=student),
        project_assignment=assignment
    ).first()
    
    return existing


def handle_direct_assignment_project(request, student, assignment):
    """Handle direct assignment project creation"""
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, current_student=student)
        if form.is_valid():
            try:
                with transaction.atomic():
                    project = form.save(commit=False)
                    
                    # Set assignment-specific fields
                    project.student = student
                    project.assignment_source = 'teacher_assigned'
                    project.project_assignment = assignment
                    project.assignment_deadline = assignment.deadline
                    project.module = assignment.module
                    project.status = 'in_progress'
                    
                    project.save()
                    form.save_m2m()  # Save collaborators
                    
                    # Record activity
                    ProjectActivity.objects.create(
                        project=project,
                        user=request.user,
                        activity_type='assignment_created',
                        description=f"Projet créé depuis le devoir: {assignment.title}"
                    )
                    
                    # Update direct assignment status
                    DirectStudentAssignment.objects.filter(
                        assignment=assignment,
                        student=student
                    ).update(status='started')
                    
                    messages.success(request, "Projet créé avec succès à partir du devoir.")
                    return redirect('student:project_detail', project_id=project.id)
                    
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        # Pre-populate form with assignment data
        initial_data = {
            'title': assignment.title,
            'description': assignment.description,
            'project_type': 'module',
            'start_date': timezone.now().date(),
            'end_date': assignment.deadline.date() if assignment.deadline else None,
            'module': assignment.module,
        }
        form = ProjectForm(initial=initial_data, current_student=student)
        
        # Make certain fields readonly since they're determined by assignment
        form.fields['module'].widget.attrs['readonly'] = True
        form.fields['project_type'].widget.attrs['readonly'] = True
    
    context = {
        'student': student,
        'assignment': assignment,
        'form': form,
        'assignment_type': 'direct',
        'team_info': {
            'is_team_work': assignment.is_team_work,
            'min_size': assignment.min_team_size,
            'max_size': assignment.max_team_size,
            'current_size': 1,  # Just the student initially
        }
    }
    
    return render(request, 'student/assignments/create_assignment_project.html', context)


def handle_choice_based_assignment_project(request, student, assignment):
    """Handle choice-based assignment project creation with option selection"""
    
    # Get available project options
    available_options = []
    for option in assignment.project_options.filter(is_available=True):
        if option.is_selectable():
            available_options.append(option)
    
    if not available_options:
        messages.error(request, "Aucune option de projet n'est disponible pour ce devoir.")
        return redirect('student:assignment_detail', assignment_id=assignment.id)
    
    selected_option_id = request.POST.get('selected_option_id') or request.GET.get('option_id')
    selected_option = None
    
    if selected_option_id:
        try:
            selected_option = ProjectOption.objects.get(
                id=selected_option_id,
                assignment=assignment,
                is_available=True
            )
            if not selected_option.is_selectable():
                messages.error(request, "Cette option n'est plus disponible.")
                return redirect('student:assignment_detail', assignment_id=assignment.id)
        except ProjectOption.DoesNotExist:
            messages.error(request, "Option de projet invalide.")
            return redirect('student:assignment_detail', assignment_id=assignment.id)
    
    if request.method == 'POST' and selected_option:
        form = ProjectForm(request.POST, current_student=student)
        if form.is_valid():
            try:
                with transaction.atomic():
                    project = form.save(commit=False)
                    
                    # Set assignment-specific fields
                    project.student = student
                    project.assignment_source = 'teacher_assigned'
                    project.project_assignment = assignment
                    project.selected_option = selected_option
                    project.assignment_deadline = assignment.deadline
                    project.module = assignment.module
                    project.status = 'in_progress'
                    
                    project.save()
                    form.save_m2m()  # Save collaborators
                    
                    # Atomically select the option (prevents race conditions)
                    selected_option.current_teams += 1
                    selected_option.save(update_fields=['current_teams'])
                    
                    # Record activity
                    ProjectActivity.objects.create(
                        project=project,
                        user=request.user,
                        activity_type='assignment_created',
                        description=f"Projet créé avec option '{selected_option.title}' pour: {assignment.title}"
                    )
                    
                    messages.success(request, f"Projet créé avec l'option '{selected_option.title}'.")
                    return redirect('student:project_detail', project_id=project.id)
                    
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        if selected_option:
            # Pre-populate form with selected option data
            initial_data = {
                'title': selected_option.title,
                'description': selected_option.description,
                'project_type': 'module',
                'start_date': timezone.now().date(),
                'end_date': assignment.deadline.date() if assignment.deadline else None,
                'module': assignment.module,
            }
        else:
            # Basic assignment data
            initial_data = {
                'title': assignment.title,
                'description': assignment.description,
                'project_type': 'module',
                'start_date': timezone.now().date(),
                'end_date': assignment.deadline.date() if assignment.deadline else None,
                'module': assignment.module,
            }
        
        form = ProjectForm(initial=initial_data, current_student=student)
        
        # Make certain fields readonly
        form.fields['module'].widget.attrs['readonly'] = True
        form.fields['project_type'].widget.attrs['readonly'] = True
        
        if selected_option:
            # If option is selected, make title and description readonly too
            form.fields['title'].widget.attrs['readonly'] = True
            form.fields['description'].widget.attrs['readonly'] = True
    
    context = {
        'student': student,
        'assignment': assignment,
        'form': form,
        'assignment_type': 'choice_based',
        'available_options': available_options,
        'selected_option': selected_option,
        'team_info': {
            'is_team_work': assignment.is_team_work,
            'min_size': assignment.min_team_size,
            'max_size': assignment.max_team_size,
            'current_size': 1,  # Just the student initially
        }
    }
    
    # Use different template sections based on whether option is selected
    if selected_option:
        return render(request, 'student/assignments/create_assignment_project.html', context)
    else:
        return render(request, 'student/assignments/select_project_option.html', context)


# COMPATIBILITY: Alias for backward compatibility with existing URLs
create_assignment_project = create_assignment_project_direct


@login_required
def select_project_option_direct(request, assignment_id):
    """Standalone option selection view for choice-based assignments"""
    student = get_student_or_error(request)
    if not student:
        return redirect('login')
    
    # Get assignment and verify access
    assignment = get_object_or_404(
        ProjectAssignment.objects.select_related('module'),
        id=assignment_id,
        module__enrollments__student=student,
        module__enrollments__is_active=True,
        status='published',
        assignment_type='choice_based'
    )
    
    # Check if student can select options
    can_create, reason = can_student_create_assignment_project(student, assignment)
    if not can_create:
        messages.error(request, reason)
        return redirect('student:assignment_detail', assignment_id=assignment.id)
    
    # Check if student already has a project for this assignment
    existing_project = get_existing_assignment_project(student, assignment)
    if existing_project:
        messages.info(request, "Vous avez déjà un projet pour ce devoir.")
        return redirect('student:project_detail', project_id=existing_project.id)
    
    # Get available options
    available_options = []
    for option in assignment.project_options.filter(is_available=True).order_by('order', 'title'):
        if option.is_selectable():
            available_options.append({
                'option': option,
                'availability': option.get_availability_text(),
                'is_selectable': True
            })
        else:
            available_options.append({
                'option': option,
                'availability': option.get_availability_text(),
                'is_selectable': False
            })
    
    if not any(opt['is_selectable'] for opt in available_options):
        messages.error(request, "Aucune option de projet n'est disponible pour ce devoir.")
        return redirect('student:assignment_detail', assignment_id=assignment.id)
    
    if request.method == 'POST':
        selected_option_id = request.POST.get('selected_option')
        if selected_option_id:
            try:
                selected_option = ProjectOption.objects.get(
                    id=selected_option_id,
                    assignment=assignment,
                    is_available=True
                )
                
                if not selected_option.is_selectable():
                    messages.error(request, "Cette option n'est plus disponible.")
                    return redirect('student:select_project_option_direct', assignment_id=assignment.id)
                
                # FIXED: Properly construct the URL with query parameters
                redirect_url = reverse('student:create_assignment_project_direct', 
                                     kwargs={'assignment_id': assignment.id})
                redirect_url += f'?option_id={selected_option.id}'
                
                return HttpResponseRedirect(redirect_url)
                
            except ProjectOption.DoesNotExist:
                messages.error(request, "Option de projet invalide.")
        else:
            messages.error(request, "Veuillez sélectionner une option de projet.")
    
    context = {
        'student': student,
        'assignment': assignment,
        'available_options': available_options,
        'team_info': {
            'is_team_work': assignment.is_team_work,
            'min_size': assignment.min_team_size,
            'max_size': assignment.max_team_size,
        }
    }
    
    return render(request, 'student/assignments/select_project_option.html', context)