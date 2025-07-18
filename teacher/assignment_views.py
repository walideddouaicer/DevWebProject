# teacher/assignment_views.py - UPDATED to use collaboration-based teams instead of groups

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, Prefetch
from django.core.exceptions import ValidationError
from django.db import models

from .models import (
    TeacherProfile, Module, ProjectAssignment, ProjectOption, 
    ModuleAssignment, ModuleEnrollment,
    DirectStudentAssignment
)
from student.models import StudentProfile, Project, Notification, ProjectActivity
from .forms import (
    ModuleCreationForm, ProjectAssignmentForm, ProjectOptionForm,
    StudentSelectionForm, AssignmentFilterForm
)

def get_teacher_or_error(request):
    """Helper function to get teacher profile with consistent error handling"""
    try:
        return TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return None

def check_teacher_module_access(teacher, module):
    """Helper function to check if teacher has access to a module"""
    return ModuleAssignment.objects.filter(
        teacher=teacher,
        module=module,
        is_active=True
    ).exists()

@login_required
def assignments_dashboard(request):
    """Main dashboard for teacher assignments - UPDATED FOR NO APPROVAL SYSTEM"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    # Get teacher's assignments with proper prefetching
    assignments = ProjectAssignment.objects.filter(
        teacher=teacher
    ).select_related('module').prefetch_related(
        Prefetch('project_options', queryset=ProjectOption.objects.filter(is_available=True)),
        Prefetch('submitted_projects', queryset=Project.objects.select_related('student__user'))
    ).order_by('module__code', '-created_at')
    
    # Apply filters
    filter_form = AssignmentFilterForm(request.GET, teacher=teacher)
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        assignment_type = filter_form.cleaned_data.get('assignment_type')
        module = filter_form.cleaned_data.get('module')
        search = filter_form.cleaned_data.get('search')
        deadline_filter = filter_form.cleaned_data.get('deadline_filter')
        
        if status:
            assignments = assignments.filter(status=status)
        if assignment_type:
            assignments = assignments.filter(assignment_type=assignment_type)
        if module:
            assignments = assignments.filter(module=module)
        if search:
            assignments = assignments.filter(title__icontains=search)
        
        # Enhanced deadline filtering
        if deadline_filter:
            now = timezone.now()
            if deadline_filter == 'upcoming':
                upcoming_deadline = now + timezone.timedelta(days=7)
                assignments = assignments.filter(
                    Q(deadline__lte=upcoming_deadline, deadline__gt=now) |
                    Q(selection_deadline__lte=upcoming_deadline, selection_deadline__gt=now)
                )
            elif deadline_filter == 'overdue':
                assignments = assignments.filter(
                    Q(deadline__lt=now) |
                    Q(selection_deadline__lt=now)
                ).exclude(status__in=['completed', 'draft'])
            elif deadline_filter == 'today':
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timezone.timedelta(days=1)
                assignments = assignments.filter(
                    Q(deadline__range=(today_start, today_end)) |
                    Q(selection_deadline__range=(today_start, today_end))
                )
    
    # Calculate statistics
    total_assignments = assignments.count()
    active_assignments = assignments.filter(status__in=['published', 'in_progress']).count()
    draft_assignments = assignments.filter(status='draft').count()
    completed_assignments = assignments.filter(status='completed').count()
    
    # Group assignments by module with proper statistics
    modules_with_assignments = {}
    for assignment in assignments:
        module = assignment.module
        if module.id not in modules_with_assignments:
            modules_with_assignments[module.id] = {
                'module': module,
                'assignments': [],
                'total_count': 0,
                'active_count': 0,
                'draft_count': 0,
                'completed_count': 0,
            }
        
        modules_with_assignments[module.id]['assignments'].append(assignment)
        modules_with_assignments[module.id]['total_count'] += 1
        
        if assignment.status in ['published', 'in_progress']:
            modules_with_assignments[module.id]['active_count'] += 1
        elif assignment.status == 'draft':
            modules_with_assignments[module.id]['draft_count'] += 1
        elif assignment.status == 'completed':
            modules_with_assignments[module.id]['completed_count'] += 1
    
    # Convert to list for template
    modules_data = list(modules_with_assignments.values())
    
    # Enhanced urgent items calculation
    urgent_assignments = []
    now = timezone.now()
    
    for assignment in assignments.filter(status__in=['published', 'in_progress']):
        urgent_items = assignment.is_deadline_approaching(days=3)
        
        for deadline_type, days_left in urgent_items:
            urgent_assignments.append({
                'assignment': assignment,
                'days_left': days_left,
                'type': {
                    'selection': "Sélection des projets", 
                    'final': "Rendu final"
                }.get(deadline_type, deadline_type),
                'deadline_type': deadline_type
            })
    
    # Sort by urgency (days left)
    urgent_assignments.sort(key=lambda x: x['days_left'])
    
    # ❌ REMOVED: No more pending module approvals
    # pending_module_approvals = 0  # No approval system anymore
    
    # Count ungraded projects
    ungraded_projects_count = Project.objects.filter(
        project_assignment__teacher=teacher,
        status='submitted'
    ).count()
    
    context = {
        'teacher': teacher,
        'assignments': assignments,
        'modules_data': modules_data,
        'filter_form': filter_form,
        'total_assignments': total_assignments,
        'active_assignments': active_assignments,
        'draft_assignments': draft_assignments,
        'completed_assignments': completed_assignments,
        'urgent_assignments': urgent_assignments[:10],
        # ❌ REMOVED: 'pending_module_approvals': 0,
        'ungraded_projects_count': ungraded_projects_count,
        'urgent_deadlines_count': len(urgent_assignments),
    }
    
    return render(request, 'teacher/assignments/dashboard.html', context)


@login_required
def assignment_detail(request, assignment_id):
    """View assignment details and progress - UPDATED FOR TEAMS WITH FULL OPTION VISIBILITY"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment.objects.select_related('module'),
        id=assignment_id,
        teacher=teacher
    )
    
    # Get all projects for this assignment
    assignment_projects = assignment.submitted_projects.select_related(
        'student__user', 'selected_option'
    ).prefetch_related('collaborators__user').order_by('-created_at')
    
    # Enhanced progress data calculation using collaboration system
    if assignment.assignment_type == 'direct':
        # For direct assignments
        direct_assignments = DirectStudentAssignment.objects.filter(
            assignment=assignment
        ).select_related('student__user')
        
        # Calculate detailed statistics
        total_assigned = direct_assignments.count()
        started_count = direct_assignments.filter(status='started').count()
        submitted_count = assignment_projects.filter(status__in=['submitted', 'validated']).count()
        validated_count = assignment_projects.filter(status='validated').count()
        overdue_count = sum(1 for da in direct_assignments if da.is_overdue())
        
        # Get individual student progress
        student_progress = []
        for direct_assignment in direct_assignments:
            project = assignment_projects.filter(student=direct_assignment.student).first()
            student_info = {
                'student': direct_assignment.student,
                'assignment_status': direct_assignment.status,
                'project': project,
                'team_size': project.get_team_size() if project else 1,
                'team_members': project.get_team_members() if project else [direct_assignment.student],
                'is_overdue': direct_assignment.is_overdue(),
                'can_submit': project.can_be_submitted_for_assignment() if project else False,
                'selected_option': project.selected_option if project else None,
            }
            student_progress.append(student_info)
        
        progress_data = {
            'total_assigned': total_assigned,
            'started': started_count,
            'submitted': submitted_count,
            'validated': validated_count,
            'overdue': overdue_count,
            'completion_rate': int((validated_count / total_assigned * 100)) if total_assigned > 0 else 0,
            'assignments': direct_assignments,
            'projects': assignment_projects,
            'student_progress': student_progress,
        }
    else:
        # For choice-based assignments - calculate teams from projects
        
        # ENHANCED: Get ALL project options with their selection status
        all_project_options = []
        for option in assignment.project_options.all().order_by('order', 'title'):
            # Get projects that selected this option
            projects_with_option = assignment_projects.filter(selected_option=option)
            
            option_data = {
                'option': option,
                'projects_count': projects_with_option.count(),
                'projects': list(projects_with_option),
                'is_available': option.is_selectable(),
                'availability_text': option.get_availability_text(),
                'teams_using': [],  # Will be populated below
            }
            
            # Get team information for each project using this option
            for project in projects_with_option:
                team_members = project.get_team_members()
                team_info = {
                    'project': project,
                    'leader': project.student,
                    'members': team_members,
                    'size': len(team_members),
                    'team_display': project.get_assignment_team_display(),
                    'status': project.status,
                    'submitted_at': project.assignment_submitted_at,
                }
                option_data['teams_using'].append(team_info)
            
            all_project_options.append(option_data)
        
        # Build team data from projects (instead of groups)
        teams_data = []
        total_students = assignment.module.get_enrolled_students_count()
        students_in_teams = set()
        
        for project in assignment_projects:
            team_members = project.get_team_members()
            team_info = {
                'project': project,
                'leader': project.student,
                'members': team_members,
                'size': len(team_members),
                'is_valid_size': project.is_team_size_valid(),
                'selected_option': project.selected_option,
                'status': project.status,
                'team_name': f"Équipe {project.title}",
                'team_display': project.get_assignment_team_display(),
            }
            teams_data.append(team_info)
            
            # Track students who are in teams
            for member in team_members:
                students_in_teams.add(member.id)
        
        # Calculate team statistics
        total_teams = len(teams_data)
        valid_teams = sum(1 for team in teams_data if team['is_valid_size'])
        submitted_teams = sum(1 for team in teams_data if team['status'] in ['submitted', 'validated'])
        
        progress_data = {
            'total_teams': total_teams,
            'valid_teams': valid_teams,
            'submitted_teams': submitted_teams,
            'total_students': total_students,
            'students_in_teams': len(students_in_teams),
            'students_without_teams': total_students - len(students_in_teams),
            'student_coverage': int((len(students_in_teams) / total_students * 100)) if total_students > 0 else 0,
            'submitted': assignment_projects.filter(status__in=['submitted', 'validated']).count(),
            'validated': assignment_projects.filter(status='validated').count(),
            'teams_data': teams_data,
            'project_options': all_project_options,  # ENHANCED: All options with selection data
            'projects': assignment_projects,
        }
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'progress_data': progress_data,
    }
    
    return render(request, 'teacher/assignments/detail.html', context)


@login_required
def assignment_teams(request, assignment_id):
    """View all teams formed through project collaboration - NEW VIEW"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment,
        id=assignment_id,
        teacher=teacher
    )
    
    # Get all projects for this assignment with their teams
    projects = assignment.submitted_projects.select_related(
        'student__user'
    ).prefetch_related('collaborators__user').order_by('-created_at')
    
    # Build comprehensive team data
    teams_data = []
    total_students_in_teams = set()
    
    for project in projects:
        team_members = project.get_team_members()
        
        # Track all students in teams
        for member in team_members:
            total_students_in_teams.add(member.id)
        
        team_info = {
            'project': project,
            'team_leader': project.student,
            'collaborators': list(project.collaborators.all()),
            'all_members': team_members,
            'team_size': len(team_members),
            'is_valid_size': project.is_team_size_valid(),
            'size_status': project.get_team_size_status(),
            'selected_option': project.selected_option,
            'status': project.status,
            'submitted_at': project.assignment_submitted_at,
            'team_display': project.get_assignment_team_display(),
            'can_submit': project.can_be_submitted_for_assignment(),
        }
        teams_data.append(team_info)
    
    # Calculate statistics
    total_enrolled = assignment.module.get_enrolled_students_count()
    students_in_teams_count = len(total_students_in_teams)
    students_without_teams = total_enrolled - students_in_teams_count
    
    # Get students who haven't joined any team yet
    unassigned_students = []
    if students_without_teams > 0:
        all_enrolled_students = StudentProfile.objects.filter(
            module_enrollments__module=assignment.module,
            module_enrollments__is_active=True
        ).select_related('user')
        
        for student in all_enrolled_students:
            if student.id not in total_students_in_teams:
                # Check if this student is eligible for this assignment
                if assignment.assignment_type == 'direct':
                    is_assigned = DirectStudentAssignment.objects.filter(
                        assignment=assignment,
                        student=student
                    ).exists()
                    if is_assigned:
                        unassigned_students.append(student)
                else:
                    unassigned_students.append(student)
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'teams_data': teams_data,
        'total_teams': len(teams_data),
        'total_enrolled': total_enrolled,
        'students_in_teams_count': students_in_teams_count,
        'students_without_teams': students_without_teams,
        'unassigned_students': unassigned_students,
        'participation_rate': int((students_in_teams_count / total_enrolled * 100)) if total_enrolled > 0 else 0,
        'valid_teams': sum(1 for team in teams_data if team['is_valid_size']),
        'submitted_teams': sum(1 for team in teams_data if team['status'] in ['submitted', 'validated']),
    }
    
    return render(request, 'teacher/assignments/teams.html', context)


@login_required
@transaction.atomic
def assignment_create(request):
    """Create a new project assignment - UPDATED TERMINOLOGY"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    # Get teacher's modules
    teacher_modules = Module.objects.filter(
        assignments__teacher=teacher,
        assignments__is_active=True,
        is_active=True
    ).distinct()
    
    if not teacher_modules.exists():
        messages.error(request, "Vous devez être assigné à au moins un module pour créer un devoir.")
        return redirect('teacher:assignments_dashboard')
    
    if request.method == 'POST':
        form = ProjectAssignmentForm(request.POST, teacher=teacher)
        module_id = request.POST.get('module')
        
        # Get selected student IDs if it's a direct assignment
        selected_student_ids = request.POST.getlist('selected_student_ids')
        
        if form.is_valid() and module_id:
            try:
                module = teacher_modules.get(id=module_id)
                
                with transaction.atomic():
                    assignment = form.save(commit=False)
                    assignment.teacher = teacher
                    assignment.module = module
                    assignment.save()
                    
                    # Handle student selection for direct assignments
                    if assignment.assignment_type == 'direct':
                        if assignment.target_selection == 'all_students':
                            # Assign to all students in module
                            enrolled_students = StudentProfile.objects.filter(
                                module_enrollments__module=module,
                                module_enrollments__is_active=True
                            )
                        elif assignment.target_selection == 'specific_students' and selected_student_ids:
                            # Assign to selected students
                            enrolled_students = StudentProfile.objects.filter(
                                id__in=selected_student_ids,
                                module_enrollments__module=module,
                                module_enrollments__is_active=True
                            )
                        else:
                            enrolled_students = StudentProfile.objects.none()
                        
                        # Create direct assignments
                        created_count = 0
                        notification_batch = []
                        
                        for student in enrolled_students:
                            direct_assignment, created = DirectStudentAssignment.objects.get_or_create(
                                assignment=assignment,
                                student=student,
                                defaults={'status': 'assigned'}
                            )
                            if created:
                                created_count += 1
                                
                                # Prepare notification for batch creation
                                notification_batch.append(
                                    Notification(
                                        recipient=student,
                                        project_assignment=assignment,
                                        notification_type='assignment_created',
                                        message=f"Nouveau devoir assigné: {assignment.title}"
                                    )
                                )
                        
                        # Batch create notifications
                        if notification_batch:
                            Notification.objects.bulk_create(notification_batch)
                        
                        if created_count > 0:
                            messages.success(request, f"Devoir créé et assigné à {created_count} étudiant(s).")
                            return redirect('teacher:assignment_detail', assignment_id=assignment.id)
                        else:
                            messages.warning(request, "Devoir créé mais aucun étudiant n'a été assigné.")
                    
                    messages.success(request, f"Devoir '{assignment.title}' créé avec succès.")
                    
                    # Redirect based on assignment type
                    if assignment.assignment_type == 'choice_based':
                        return redirect('teacher:assignment_options', assignment_id=assignment.id)
                    else:
                        return redirect('teacher:assignment_detail', assignment_id=assignment.id)
                        
            except Module.DoesNotExist:
                messages.error(request, "Module sélectionné invalide.")
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            if not module_id:
                messages.error(request, "Veuillez sélectionner un module.")
    else:
        form = ProjectAssignmentForm(teacher=teacher)
    
    context = {
        'teacher': teacher,
        'form': form,
        'teacher_modules': teacher_modules,
    }
    
    return render(request, 'teacher/assignments/create.html', context)


@login_required
@transaction.atomic
def assignment_options(request, assignment_id):
    """Manage project options for choice-based assignments"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment,
        id=assignment_id,
        teacher=teacher,
        assignment_type='choice_based'
    )
    
    if request.method == 'POST':
        form = ProjectOptionForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    option = form.save(commit=False)
                    option.assignment = assignment
                    
                    # Set order automatically
                    max_order = assignment.project_options.aggregate(
                        max_order=models.Max('order')
                    )['max_order'] or 0
                    option.order = max_order + 1
                    
                    option.save()
                    
                    messages.success(request, f"Option de projet '{option.title}' ajoutée.")
                    return redirect('teacher:assignment_options', assignment_id=assignment.id)
                    
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = ProjectOptionForm()
    
    project_options = assignment.project_options.all().order_by('order')
    
    # Add statistics for each option using project system
    options_with_stats = []
    for option in project_options:
        # Count projects that selected this option
        projects_count = Project.objects.filter(
            project_assignment=assignment,
            selected_option=option
        ).count()
        
        options_with_stats.append({
            'option': option,
            'projects_count': projects_count,  # Changed from groups_count
            'availability_status': option.get_availability_text(),
            'can_be_deleted': projects_count == 0,  # Can only delete if no projects selected it
        })
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'project_options': project_options,
        'options_with_stats': options_with_stats,
        'form': form,
    }
    
    return render(request, 'teacher/assignments/options.html', context)


@login_required
@transaction.atomic
def assignment_students(request, assignment_id):
    """Select students for direct assignments"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment,
        id=assignment_id,
        teacher=teacher,
        assignment_type='direct'
    )
    
    if request.method == 'POST':
        form = StudentSelectionForm(request.POST, module=assignment.module)
        if form.is_valid():
            selected_students = form.cleaned_data['selected_students']
            select_all = form.cleaned_data.get('select_all', False)
            
            try:
                with transaction.atomic():
                    if select_all or assignment.target_selection == 'all_students':
                        # Assign to all students in module
                        enrolled_students = StudentProfile.objects.filter(
                            module_enrollments__module=assignment.module,
                            module_enrollments__is_active=True
                        )
                        students_to_assign = enrolled_students
                    else:
                        # Assign to selected students
                        students_to_assign = selected_students
                    
                    # Create direct assignments
                    created_count = 0
                    notification_batch = []
                    
                    for student in students_to_assign:
                        direct_assignment, created = DirectStudentAssignment.objects.get_or_create(
                            assignment=assignment,
                            student=student,
                            defaults={'status': 'assigned'}
                        )
                        if created:
                            created_count += 1
                            
                            # Prepare notification for batch creation
                            notification_batch.append(
                                Notification(
                                    recipient=student,
                                    project_assignment=assignment,
                                    notification_type='assignment_created',
                                    message=f"Nouveau devoir assigné: {assignment.title}"
                                )
                            )
                    
                    # Batch create notifications for better performance
                    if notification_batch:
                        Notification.objects.bulk_create(notification_batch)
                    
                    messages.success(request, f"{created_count} étudiants assignés au devoir.")
                    return redirect('teacher:assignment_detail', assignment_id=assignment.id)
                    
            except Exception as e:
                messages.error(request, f"Erreur lors de l'assignation: {str(e)}")
    else:
        form = StudentSelectionForm(module=assignment.module)
    
    # Get already assigned students
    assigned_students = DirectStudentAssignment.objects.filter(
        assignment=assignment
    ).select_related('student__user')
    
    # Get module enrollment statistics
    total_enrolled = assignment.module.get_enrolled_students_count()
    total_assigned = assigned_students.count()
    unassigned_count = total_enrolled - total_assigned
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'form': form,
        'assigned_students': assigned_students,
        'total_enrolled': total_enrolled,
        'total_assigned': total_assigned,
        'unassigned_count': unassigned_count,
    }
    
    return render(request, 'teacher/assignments/students.html', context)


@login_required
@transaction.atomic
def assignment_publish(request, assignment_id):
    """Publish an assignment"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment,
        id=assignment_id,
        teacher=teacher,
        status='draft'
    )
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Enhanced validation before publishing
                validation_errors = []
                
                # Check assignment completeness
                if not assignment.can_be_published():
                    if assignment.assignment_type == 'choice_based':
                        if not assignment.project_options.exists():
                            validation_errors.append("Vous devez ajouter au moins une option de projet pour les devoirs à choix multiple.")
                        else:
                            available_options = assignment.project_options.filter(is_available=True).count()
                            if available_options == 0:
                                validation_errors.append("Aucune option de projet n'est disponible.")
                    
                    if assignment.assignment_type == 'direct':
                        if not assignment.direct_assignments.exists():
                            validation_errors.append("Vous devez assigner des étudiants avant de publier le devoir.")
                
                # Check deadlines are still valid
                now = timezone.now()
                if assignment.deadline <= now:
                    validation_errors.append("La date limite de rendu doit être dans le futur.")
                
                if assignment.selection_deadline and assignment.selection_deadline <= now:
                    validation_errors.append("La date limite de sélection des projets doit être dans le futur.")
                
                if validation_errors:
                    for error in validation_errors:
                        messages.error(request, error)
                    return redirect('teacher:assignment_detail', assignment_id=assignment.id)
                
                # Publish the assignment
                assignment.published_at = timezone.now()
                assignment.status = 'published'
                assignment.save(update_fields=['published_at', 'status'])
                
                # Optimized notification creation
                notification_batch = []
                
                if assignment.assignment_type == 'direct':
                    # Notify assigned students
                    assigned_students = DirectStudentAssignment.objects.filter(
                        assignment=assignment
                    ).select_related('student')
                    
                    for direct_assignment in assigned_students:
                        notification_batch.append(
                            Notification(
                                recipient=direct_assignment.student,
                                project_assignment=assignment,
                                notification_type='assignment_created',
                                message=f"Nouveau devoir disponible: {assignment.title}"
                            )
                        )
                else:
                    # Notify all students in module
                    enrolled_students = StudentProfile.objects.filter(
                        module_enrollments__module=assignment.module,
                        module_enrollments__is_active=True
                    )
                    
                    for student in enrolled_students:
                        notification_batch.append(
                            Notification(
                                recipient=student,
                                project_assignment=assignment,
                                notification_type='assignment_created',
                                message=f"Nouveau devoir disponible: {assignment.title}"
                            )
                        )
                
                # Batch create notifications
                if notification_batch:
                    Notification.objects.bulk_create(notification_batch)
                
                messages.success(request, f"Devoir '{assignment.title}' publié avec succès.")
                return redirect('teacher:assignment_detail', assignment_id=assignment.id)
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la publication: {str(e)}")
    
    # Get assignment readiness information
    readiness_info = {
        'has_options': False,
        'has_students': False,
        'valid_deadlines': True,
        'total_students': 0,
        'total_options': 0,
    }
    
    if assignment.assignment_type == 'choice_based':
        readiness_info['total_options'] = assignment.project_options.filter(is_available=True).count()
        readiness_info['has_options'] = readiness_info['total_options'] > 0
    else:
        readiness_info['total_students'] = assignment.direct_assignments.count()
        readiness_info['has_students'] = readiness_info['total_students'] > 0
    
    # Check deadline validity
    now = timezone.now()
    readiness_info['valid_deadlines'] = (
        assignment.deadline > now and
        (not assignment.selection_deadline or assignment.selection_deadline > now)
    )
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'readiness_info': readiness_info,
    }
    
    return render(request, 'teacher/assignments/publish_confirm.html', context)


@login_required
def assignment_progress(request, assignment_id):
    """View detailed progress of an assignment"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment,
        id=assignment_id,
        teacher=teacher
    )
    
    # Get submitted projects for this assignment with proper filtering
    submitted_projects = assignment.submitted_projects.select_related(
        'student__user'
    ).prefetch_related('collaborators__user').order_by('-updated_at')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    if status_filter:
        submitted_projects = submitted_projects.filter(status=status_filter)
    
    if search_query:
        submitted_projects = submitted_projects.filter(
            Q(title__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query) |
            Q(student__user__username__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(submitted_projects, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Enhanced statistics calculation
    if assignment.assignment_type == 'direct':
        total_expected = assignment.direct_assignments.count()
        assigned_count = assignment.direct_assignments.filter(status='assigned').count()
        started_count = assignment.direct_assignments.filter(status='started').count()
        submitted_count = assignment.direct_assignments.filter(status='submitted').count()
        validated_count = assignment.direct_assignments.filter(status='validated').count()
    else:
        # For choice-based assignments, count teams instead of groups
        total_projects = assignment.submitted_projects.count()
        total_expected = total_projects
        assigned_count = 0  # Not applicable for choice-based
        started_count = assignment.submitted_projects.filter(status='in_progress').count()
        submitted_count = assignment.submitted_projects.filter(status='submitted').count()
        validated_count = assignment.submitted_projects.filter(status='validated').count()
    
    completion_rate = int((validated_count / total_expected * 100)) if total_expected > 0 else 0
    submission_rate = int((submitted_count / total_expected * 100)) if total_expected > 0 else 0
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_expected': total_expected,
        'assigned_count': assigned_count,
        'started_count': started_count,
        'submitted_count': submitted_count,
        'validated_count': validated_count,
        'completion_rate': completion_rate,
        'submission_rate': submission_rate,
        'status_choices': Project.STATUS_CHOICES,
    }
    
    return render(request, 'teacher/assignments/progress.html', context)


@login_required
def assignment_edit(request, assignment_id):
    """Edit assignment details"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(
        ProjectAssignment,
        id=assignment_id,
        teacher=teacher
    )
    
    # Enhanced edit permissions check
    can_edit = assignment.status in ['draft', 'published']
    has_student_activity = False
    
    if assignment.status == 'published':
        # Check if students have started working (using project system)
        has_student_activity = assignment.submitted_projects.exists()
        
        if has_student_activity:
            # Limited editing for published assignments with activity
            edit_type = 'limited'
        else:
            edit_type = 'full'
    else:
        edit_type = 'full'
    
    if not can_edit:
        messages.error(request, "Ce devoir ne peut plus être modifié.")
        return redirect('teacher:assignment_detail', assignment_id=assignment.id)
    
    if request.method == 'POST':
        # For limited editing, only allow certain fields
        if edit_type == 'limited':
            assignment.description = request.POST.get('description', assignment.description)
            assignment.instructions = request.POST.get('instructions', assignment.instructions)
            try:
                assignment.save(update_fields=['description', 'instructions'])
                messages.success(request, "Devoir mis à jour avec succès.")
                return redirect('teacher:assignment_detail', assignment_id=assignment.id)
            except Exception as e:
                messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")
        else:
            form = ProjectAssignmentForm(request.POST, instance=assignment, teacher=teacher)
            if form.is_valid():
                try:
                    assignment = form.save()
                    messages.success(request, "Devoir mis à jour avec succès.")
                    return redirect('teacher:assignment_detail', assignment_id=assignment.id)
                except ValidationError as e:
                    messages.error(request, str(e))
    else:
        if edit_type == 'limited':
            form = None  # Will show simple form in template
        else:
            form = ProjectAssignmentForm(instance=assignment, teacher=teacher)
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'form': form,
        'edit_type': edit_type,
        'has_student_activity': has_student_activity,
    }
    
    return render(request, 'teacher/assignments/edit.html', context)


@login_required
@transaction.atomic
def option_delete(request, assignment_id, option_id):
    """Delete a project option"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    assignment = get_object_or_404(ProjectAssignment, id=assignment_id, teacher=teacher)
    option = get_object_or_404(ProjectOption, id=option_id, assignment=assignment)
    
    # Enhanced deletion validation using project system
    projects_using_option = Project.objects.filter(selected_option=option).count()
    
    if projects_using_option > 0:
        messages.error(request, 
            f"Cette option ne peut pas être supprimée car elle est utilisée par "
            f"{projects_using_option} projet(s)."
        )
        return redirect('teacher:assignment_options', assignment_id=assignment.id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                option_title = option.title
                option.delete()
                
                messages.success(request, f"Option '{option_title}' supprimée avec succès.")
                return redirect('teacher:assignment_options', assignment_id=assignment.id)
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
    
    context = {
        'teacher': teacher,
        'assignment': assignment,
        'option': option,
        'projects_using_option': projects_using_option,
    }
    
    return render(request, 'teacher/assignments/option_delete_confirm.html', context)


@login_required
@transaction.atomic
def create_teacher_module(request):
    """Allow teachers to create new modules directly (no approval needed)"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    if request.method == 'POST':
        form = ModuleCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    module = form.save(commit=False)
                    module.primary_teacher = teacher
                    module.created_by_teacher = True
                    module.requires_approval = False  # CHANGED: No approval needed
                    module.is_active = True           # CHANGED: Active immediately
                    module.approved_by = None         # CHANGED: No approval needed
                    module.approved_at = timezone.now()  # CHANGED: Auto-approved
                    module.save()
                    
                    # Automatically assign the teacher to the module
                    ModuleAssignment.objects.create(
                        teacher=teacher,
                        module=module,
                        assigned_by=teacher.user,  # Self-assigned
                        is_active=True
                    )
                    
                    # ❌ REMOVED: ProjectActivity creation (was causing the error)
                    # No need to log module creation as project activity
                    
                    messages.success(
                        request, 
                        f"✅ Module '{module.code} - {module.name}' créé avec succès! "
                        f"Votre module est maintenant actif et les étudiants peuvent s'inscrire."
                    )
                    return redirect('teacher:module_detail', module_id=module.id)
                    
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Erreur lors de la création: {str(e)}")
    else:
        form = ModuleCreationForm()
    
    context = {
        'teacher': teacher,
        'form': form,
    }
    
    return render(request, 'teacher/modules/create.html', context)


@login_required
def my_modules(request):
    """Display teacher's modules - updated for direct creation"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect('login')
    
    # Get teacher's assigned modules (both admin-assigned and self-created)
    module_assignments = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).select_related('module').order_by('-assigned_at')
    
    modules_with_stats = []
    for assignment in module_assignments:
        module = assignment.module
        
        # Calculate statistics
        enrolled_count = ModuleEnrollment.objects.filter(
            module=module,
            is_active=True
        ).count()
        
        project_assignments_count = ProjectAssignment.objects.filter(
            teacher=teacher,
            module=module
        ).count()
        
        total_projects_count = Project.objects.filter(
            module=module
        ).count()
        
        # Get recent students for preview
        recent_students = ModuleEnrollment.objects.filter(
            module=module,
            is_active=True
        ).select_related('student__user').order_by('-enrolled_at')[:10]
        
        modules_with_stats.append({
            'assignment': assignment,
            'module': module,
            'enrolled_count': enrolled_count,
            'project_assignments_count': project_assignments_count,
            'total_projects_count': total_projects_count,
            'recent_students': recent_students,
            'is_self_created': module.created_by_teacher and module.primary_teacher == teacher,
            'creation_status': 'active',  # Always active now
        })
    
    context = {
        'teacher': teacher,
        'modules_with_stats': modules_with_stats,
        'pending_modules_count': 0,  # No more pending modules
    }
    
    return render(request, 'teacher/modules/my_modules.html', context)
