from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from .assignment_views import *
from .models import TeacherProfile, Module, ModuleAssignment, ModuleEnrollment
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@login_required
def dashboard(request):
    """Enhanced teacher dashboard with module and project data"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant. Contactez l'administrateur.")
        return redirect('login')
    
    # Get teacher's assigned modules
    assigned_modules = ModuleAssignment.objects.filter(
        teacher=teacher, 
        is_active=True
    ).select_related('module')
    
    # Get teacher's module IDs
    teacher_module_ids = assigned_modules.values_list('module', flat=True)
    
    # Import here to avoid circular imports
    from student.models import Project
    
    # Get projects from teacher's modules
    teacher_projects = Project.objects.filter(module__in=teacher_module_ids)
    
    # Calculate statistics
    total_modules = assigned_modules.count()
    total_students = 0
    total_projects = teacher_projects.count()  # MISSING: Add this line
    pending_projects = teacher_projects.filter(status='submitted').count()
    validated_projects = teacher_projects.filter(status='validated').count()
    
    # Count total students across all modules
    for assignment in assigned_modules:
        total_students += assignment.module.get_enrolled_students_count()
    
    # Get recent modules for display
    recent_modules = assigned_modules[:5]  # Show 5 most recent
    
    # Get recent projects for the activity section
    recent_projects = teacher_projects.select_related(
        'student__user', 'module'
    ).order_by('-updated_at')[:5]  # MISSING: Add this line
    
    context = {
        'teacher': teacher,
        'total_modules': total_modules,
        'total_students': total_students,
        'total_projects': total_projects,  # MISSING: Add this line
        'pending_projects': pending_projects,
        'validated_projects': validated_projects,
        'recent_modules': recent_modules,
        'recent_projects': recent_projects,  # MISSING: Add this line
        'assigned_modules': assigned_modules,
    }
    
    return render(request, 'teacher/dashboard.html', context)

@login_required
def modules_list(request):
    """View to display all modules assigned to the teacher"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant. Contactez l'administrateur.")
        return redirect('login')
    
    # Get all assigned modules with related data
    assigned_modules = ModuleAssignment.objects.filter(
        teacher=teacher, 
        is_active=True
    ).select_related('module').prefetch_related('module__enrollments__student__user')
    
    context = {
        'teacher': teacher,
        'assigned_modules': assigned_modules,
    }
    
    return render(request, 'teacher/modules_list.html', context)









# ADD these missing functions to the END of your teacher/views.py file

@login_required
def module_detail(request, module_id):
    """Detailed view of a specific module"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Verify teacher has access to this module
    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher,
            module_id=module_id,
            is_active=True
        )
        module = assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect('teacher:modules_list')
    
    # Get module statistics
    enrollments = ModuleEnrollment.objects.filter(
        module=module,
        is_active=True
    ).select_related('student__user')
    
    # Import here to avoid circular imports
    from student.models import Project
    
    # Get projects from this module
    module_projects = Project.objects.filter(
        module=module
    ).select_related('student__user').order_by('-updated_at')
    
    # Statistics
    total_students = enrollments.count()
    total_projects = module_projects.count()
    submitted_projects = module_projects.filter(status='submitted').count()
    validated_projects = module_projects.filter(status='validated').count()
    
    context = {
        'teacher': teacher,
        'module': module,
        'assignment': assignment,
        'enrollments': enrollments,
        'module_projects': module_projects[:10],  # Show recent 10
        'total_students': total_students,
        'total_projects': total_projects,
        'submitted_projects': submitted_projects,
        'validated_projects': validated_projects,
    }
    
    return render(request, 'teacher/module_detail.html', context)

@login_required
def module_projects(request, module_id):
    """View all projects for a specific module"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Verify teacher has access to this module
    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher,
            module_id=module_id,
            is_active=True
        )
        module = assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect('teacher:modules_list')
    
    # Import here to avoid circular imports
    from student.models import Project
    
    # Get all projects from this module
    projects = Project.objects.filter(
        module=module
    ).select_related('student__user').order_by('-updated_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status', '')
    if status_filter:
        projects = projects.filter(status=status_filter)
    
    # Statistics
    total_projects = projects.count()
    submitted_projects = projects.filter(status='submitted').count()
    validated_projects = projects.filter(status='validated').count()
    rejected_projects = projects.filter(status='rejected').count()
    
    context = {
        'teacher': teacher,
        'module': module,
        'projects': projects,
        'total_projects': total_projects,
        'submitted_projects': submitted_projects,
        'validated_projects': validated_projects,
        'rejected_projects': rejected_projects,
        'status_filter': status_filter,
    }
    
    return render(request, 'teacher/module_projects.html', context)

# REPLACE the module_management function in teacher/views.py with this FIXED version:

@login_required
def module_management(request, module_id):
    """Module management interface for teachers"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Verify teacher has access to this module
    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher,
            module_id=module_id,
            is_active=True
        )
        module = assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect('teacher:modules_list')
    
    # Get enrollments - Fixed query
    try:
        enrollments = ModuleEnrollment.objects.filter(
            module=module,
            is_active=True
        ).select_related('student__user')
        
        # Add debug info
        print(f"DEBUG: Found {enrollments.count()} enrollments for module {module.code}")
        
    except Exception as e:
        print(f"DEBUG: Error getting enrollments: {e}")
        enrollments = []
    
    context = {
        'teacher': teacher,
        'module': module,
        'assignment': assignment,
        'enrollments': enrollments,
    }
    
    # Ensure we always return a response
    try:
        return render(request, 'teacher/module_management.html', context)
    except Exception as e:
        print(f"DEBUG: Template render error: {e}")
        # Fallback response
        return render(request, 'teacher/base.html', {
            'error_message': f'Error loading module management for {module.code}. Template issue.'
        })
























# new functions that handle project feedback

@login_required
def student_projects(request):
    """View all student projects from teacher's modules"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Get all modules assigned to this teacher
    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)
    
    # Import here to avoid circular imports
    from student.models import Project
    
    # Get projects from students in teacher's modules
    projects = Project.objects.filter(
        module__in=teacher_modules
    ).select_related(
        'student__user', 'module'
    ).prefetch_related(
        'collaborators__user'
    ).order_by('-updated_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status', '')
    if status_filter:
        projects = projects.filter(status=status_filter)
    
    # Filter by module if requested
    module_filter = request.GET.get('module', '')
    if module_filter:
        projects = projects.filter(module__id=module_filter)
    
    # Get statistics
    total_projects = projects.count()
    submitted_projects = projects.filter(status='submitted').count()
    validated_projects = projects.filter(status='validated').count()
    rejected_projects = projects.filter(status='rejected').count()
    
    # Get teacher's modules for filter dropdown
    modules = Module.objects.filter(id__in=teacher_modules)
    
    context = {
        'teacher': teacher,
        'projects': projects,
        'total_projects': total_projects,
        'submitted_projects': submitted_projects,
        'validated_projects': validated_projects,
        'rejected_projects': rejected_projects,
        'modules': modules,
        'status_filter': status_filter,
        'module_filter': module_filter,
    }
    
    return render(request, 'teacher/student_projects.html', context)

# In teacher/views.py, replace the project_review function with this fixed version:

@login_required
def project_review(request, project_id):
    """Detailed view for teacher to review a student project"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Get teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)
    
    # Import here to avoid circular imports
    from student.models import Project, ProjectComment
    
    # Get project (only if it's in teacher's modules)
    project = get_object_or_404(
        Project.objects.select_related('student__user', 'module'),
        id=project_id,
        module__in=teacher_modules
    )
    
    # Get project details - FIXED: Remove the problematic select_related calls
    deliverables = project.deliverables.all().prefetch_related('feedback_comments__author')
    milestones = project.milestones.all()
    comments = project.comments.all().select_related('author')  # Fixed: now just 'author' since it's User
    activities = project.activities.all().select_related('user')
    
    context = {
        'teacher': teacher,
        'project': project,
        'deliverables': deliverables,
        'milestones': milestones,
        'comments': comments,
        'activities': activities,
        'evaluation': getattr(project, 'evaluation', None),
    }

    return render(request, 'teacher/project_review.html', context)


@login_required
def approve_project(request, project_id):
    """Teacher approves a student project"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Get teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)
    
    # Import here
    from student.models import Project, ProjectActivity, Notification
    from .models import DirectStudentAssignment

    project = get_object_or_404(
        Project,
        id=project_id,
        module__in=teacher_modules,
        status='submitted'
    )

    project.status = 'validated'
    project.save()

    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description=f"Projet validé par {teacher.user.get_full_name() or teacher.user.username}"
    )

    teacher_name = teacher.user.get_full_name() or teacher.user.username

    # Notify the whole team (owner + collaborators)
    for member in project.get_team_members():
        Notification.objects.create(
            recipient=member,
            project=project,
            notification_type='project_update',
            message=f"Le projet '{project.title}' a été validé par {teacher_name}"
        )

    # Keep direct-assignment tracking in sync for the whole team
    if project.is_assignment_project() and project.project_assignment.assignment_type == 'direct':
        DirectStudentAssignment.objects.filter(
            assignment=project.project_assignment,
            student__in=[member.id for member in project.get_team_members()]
        ).update(status='validated')

    messages.success(request, f"Projet '{project.title}' validé avec succès.")
    return redirect('teacher:project_review', project_id=project.id)

@login_required
def reject_project(request, project_id):
    """Teacher rejects a student project"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Get teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)
    
    # Import here
    from student.models import Project, ProjectActivity, Notification
    from .models import DirectStudentAssignment

    project = get_object_or_404(
        Project,
        id=project_id,
        module__in=teacher_modules,
        status='submitted'
    )

    project.status = 'rejected'
    project.save()

    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description=f"Projet rejeté par {teacher.user.get_full_name() or teacher.user.username}"
    )

    # Notify the whole team (owner + collaborators)
    for member in project.get_team_members():
        Notification.objects.create(
            recipient=member,
            project=project,
            notification_type='project_update',
            message=f"Le projet '{project.title}' a été rejeté. Consultez les commentaires du projet pour plus de détails."
        )

    # The team goes back to work: reset direct-assignment tracking
    if project.is_assignment_project() and project.project_assignment.assignment_type == 'direct':
        DirectStudentAssignment.objects.filter(
            assignment=project.project_assignment,
            student__in=[member.id for member in project.get_team_members()]
        ).update(status='started')
    
    messages.success(request, f"Projet '{project.title}' rejeté. L'étudiant peut maintenant le modifier et resoumettre.")
    return redirect('teacher:project_review', project_id=project.id)

@login_required
def request_revision(request, project_id):
    """Teacher requests revisions on a submitted project (between approve and reject)"""
    if request.method != 'POST':
        return redirect('teacher:project_review', project_id=project_id)

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')

    # Get teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)

    # Import here
    from student.models import Project, ProjectComment, ProjectActivity, Notification

    project = get_object_or_404(
        Project,
        id=project_id,
        module__in=teacher_modules,
        status='submitted'
    )

    content = request.POST.get('content', '').strip()
    if not content:
        messages.error(request, "Veuillez préciser les modifications attendues avant de demander une révision.")
        return redirect('teacher:project_review', project_id=project.id)

    teacher_name = teacher.user.get_full_name() or teacher.user.username

    project.status = 'revision_requested'
    project.save()

    # The requested changes are recorded as a project comment
    ProjectComment.objects.create(
        project=project,
        author=request.user,
        content=f"[RÉVISION DEMANDÉE]\n{content}"
    )

    # Record activity
    ProjectActivity.objects.create(
        project=project,
        user=request.user,
        activity_type='status_changed',
        description=f"Révision demandée par {teacher_name}"
    )

    # Notify the whole team
    for member in project.get_team_members():
        Notification.objects.create(
            recipient=member,
            project=project,
            notification_type='project_update',
            message=f"{teacher_name} demande des révisions sur le projet '{project.title}'. Consultez ses commentaires puis resoumettez."
        )

    messages.success(request, f"Révision demandée pour '{project.title}'. L'étudiant a été notifié.")
    return redirect('teacher:project_review', project_id=project.id)


@login_required
def add_deliverable_comment(request, deliverable_id):
    """Teacher adds feedback on a specific deliverable"""
    from student.models import ProjectDeliverable, DeliverableComment, Notification

    deliverable = get_object_or_404(ProjectDeliverable, id=deliverable_id)
    project = deliverable.project

    if request.method != 'POST':
        return redirect('teacher:project_review', project_id=project.id)

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')

    # Verify the deliverable belongs to a project in the teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)

    if project.module_id not in teacher_modules:
        messages.error(request, "Vous n'avez pas accès à ce projet.")
        return redirect('teacher:student_projects')

    content = request.POST.get('content', '').strip()
    if not content:
        messages.error(request, "Le commentaire ne peut pas être vide.")
        return redirect('teacher:project_review', project_id=project.id)

    DeliverableComment.objects.create(
        deliverable=deliverable,
        author=request.user,
        content=content
    )

    teacher_name = teacher.user.get_full_name() or teacher.user.username
    for member in project.get_team_members():
        Notification.objects.create(
            recipient=member,
            project=project,
            notification_type='deliverable',
            message=f"{teacher_name} a commenté le livrable '{deliverable.name}' du projet '{project.title}'"
        )

    messages.success(request, f"Commentaire ajouté sur le livrable '{deliverable.name}'.")
    return redirect('teacher:project_review', project_id=project.id)


@login_required
def add_teacher_comment(request, project_id):
    """Teacher adds a comment to a student project"""
    if request.method != 'POST':
        return redirect('teacher:project_review', project_id=project_id)
    
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')
    
    # Get teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)
    
    # Import here
    from student.models import Project, ProjectComment, Notification
    
    project = get_object_or_404(
        Project,
        id=project_id,
        module__in=teacher_modules
    )
    
    content = request.POST.get('content')
    if content:
        try:
            # Create comment with teacher as author (now using User model)
            comment = ProjectComment.objects.create(
                project=project,
                author=request.user,  # Now using User directly
                content=f"[FEEDBACK ENSEIGNANT]\n{content}"
            )
            
            # Notify student
            Notification.objects.create(
                recipient=project.student,
                project=project,
                notification_type='project_update',
                message=f"Nouveau commentaire de {teacher.user.get_full_name() or teacher.user.username} sur votre projet '{project.title}'"
            )
            
            # Notify collaborators too
            for collaborator in project.collaborators.all():
                Notification.objects.create(
                    recipient=collaborator,
                    project=project,
                    notification_type='project_update',
                    message=f"Nouveau commentaire de {teacher.user.get_full_name() or teacher.user.username} sur le projet '{project.title}'"
                )
            
            messages.success(request, "Commentaire ajouté avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'ajout du commentaire: {str(e)}")
    else:
        messages.error(request, "Le commentaire ne peut pas être vide.")
    
    return redirect('teacher:project_review', project_id=project.id)

# Excel exports (ROADMAP #7)

@login_required
def export_module_roster(request, module_id):
    """Download the module's enrolled-students list as Excel."""
    from administrator.exports import build_module_roster_workbook, excel_response
    from django.utils import timezone

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')

    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
        )
        module = assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect('teacher:modules_list')

    enrollments = ModuleEnrollment.objects.filter(
        module=module, is_active=True
    ).select_related('student__user').order_by('student__user__last_name')

    workbook = build_module_roster_workbook(module, enrollments)
    filename = f"etudiants_{module.code}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    return excel_response(workbook, filename)


@login_required
def export_assignment_results(request, assignment_id):
    """Download an assignment's teams, statuses and grades as Excel."""
    from administrator.exports import build_assignment_results_workbook, excel_response
    from .models import ProjectAssignment
    from django.utils import timezone

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')

    assignment = get_object_or_404(
        ProjectAssignment, id=assignment_id, teacher=teacher
    )

    projects = assignment.submitted_projects.select_related(
        'student__user', 'selected_option'
    ).prefetch_related('collaborators__user').order_by('student__user__last_name')

    workbook = build_assignment_results_workbook(assignment, projects)
    safe_title = ''.join(ch if ch.isalnum() else '_' for ch in assignment.title)[:40]
    filename = f"resultats_{safe_title}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    return excel_response(workbook, filename)


# Bulk submission actions (ROADMAP #5)

@login_required
@require_http_methods(["POST"])
def bulk_project_action(request, assignment_id):
    """Validate or request revision on several submitted projects at once."""
    from .models import ProjectAssignment, DirectStudentAssignment
    from student.models import Project, ProjectComment, ProjectActivity, Notification

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')

    assignment = get_object_or_404(
        ProjectAssignment, id=assignment_id, teacher=teacher
    )

    action = request.POST.get('action')
    project_ids = request.POST.getlist('project_ids')
    content = request.POST.get('content', '').strip()
    teacher_name = teacher.user.get_full_name() or teacher.user.username

    if action not in ('validate', 'revision'):
        messages.error(request, "Action groupée invalide.")
        return redirect('teacher:assignment_progress', assignment_id=assignment.id)

    if not project_ids:
        messages.warning(request, "Aucun projet sélectionné.")
        return redirect('teacher:assignment_progress', assignment_id=assignment.id)

    if action == 'revision' and not content:
        messages.error(request, "Veuillez préciser les modifications attendues pour demander une révision groupée.")
        return redirect('teacher:assignment_progress', assignment_id=assignment.id)

    # Only submitted projects of THIS assignment can be processed
    projects = Project.objects.filter(
        id__in=project_ids,
        project_assignment=assignment,
        status='submitted'
    )

    processed = 0
    for project in projects:
        if action == 'validate':
            project.status = 'validated'
            project.save()

            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type='status_changed',
                description=f"Projet validé par {teacher_name} (action groupée)"
            )

            if project.is_assignment_project() and assignment.assignment_type == 'direct':
                DirectStudentAssignment.objects.filter(
                    assignment=assignment,
                    student__in=[member.id for member in project.get_team_members()]
                ).update(status='validated')

            for member in project.get_team_members():
                Notification.objects.create(
                    recipient=member,
                    project=project,
                    notification_type='project_update',
                    message=f"Le projet '{project.title}' a été validé par {teacher_name}"
                )
        else:  # revision
            project.status = 'revision_requested'
            project.save()

            ProjectComment.objects.create(
                project=project,
                author=request.user,
                content=f"[RÉVISION DEMANDÉE]\n{content}"
            )
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type='status_changed',
                description=f"Révision demandée par {teacher_name} (action groupée)"
            )
            for member in project.get_team_members():
                Notification.objects.create(
                    recipient=member,
                    project=project,
                    notification_type='project_update',
                    message=f"{teacher_name} demande des révisions sur le projet '{project.title}'. Consultez ses commentaires puis resoumettez."
                )
        processed += 1

    skipped = len(project_ids) - processed
    if action == 'validate':
        messages.success(request, f"{processed} projet(s) validé(s).")
    else:
        messages.success(request, f"Révision demandée pour {processed} projet(s).")
    if skipped:
        messages.warning(request, f"{skipped} projet(s) ignoré(s) (non soumis ou hors de ce devoir).")

    return redirect('teacher:assignment_progress', assignment_id=assignment.id)


# Grading / evaluation (ROADMAP #4)

DEFAULT_EVALUATION_CRITERIA = [
    "Qualité technique",
    "Livrables & documentation",
    "Respect des délais",
    "Présentation & clarté",
]


def _parse_score(raw):
    """Parse a /20 score; accepts French comma decimals. Returns Decimal or None."""
    from decimal import Decimal, InvalidOperation
    raw = (raw or '').strip().replace(',', '.')
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if not (0 <= value <= 20):
        return None
    return value


@login_required
def grade_project(request, project_id):
    """Grade a project: overall score /20, appreciation, per-criterion rubric."""
    from .models import ProjectEvaluation, EvaluationCriterion, DirectStudentAssignment
    from student.models import Project, ProjectActivity, Notification

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect('login')

    teacher_modules = ModuleAssignment.objects.filter(
        teacher=teacher,
        is_active=True
    ).values_list('module', flat=True)

    project = get_object_or_404(
        Project.objects.select_related('student__user', 'module'),
        id=project_id,
        module__in=teacher_modules
    )

    if project.status not in ['submitted', 'validated']:
        messages.warning(request, "Seuls les projets soumis ou validés peuvent être notés.")
        return redirect('teacher:project_review', project_id=project.id)

    evaluation = getattr(project, 'evaluation', None)
    teacher_name = teacher.user.get_full_name() or teacher.user.username

    if request.method == 'POST':
        score = _parse_score(request.POST.get('score'))
        comments = request.POST.get('comments', '').strip()
        validate_project = request.POST.get('validate_project') == 'on'

        # Parse rubric rows (parallel arrays); empty rows are skipped
        names = request.POST.getlist('criterion_name')
        scores = request.POST.getlist('criterion_score')
        criterion_comments = request.POST.getlist('criterion_comment')

        criteria_rows = []
        errors = []
        if score is None:
            errors.append("La note globale est obligatoire et doit être comprise entre 0 et 20.")

        for i, name in enumerate(names):
            name = name.strip()
            raw_score = scores[i] if i < len(scores) else ''
            comment = (criterion_comments[i] if i < len(criterion_comments) else '').strip()
            if not name and not raw_score.strip():
                continue  # fully empty row
            crit_score = _parse_score(raw_score)
            if not name:
                errors.append(f"Le critère n°{i + 1} a une note mais pas de nom.")
            elif crit_score is None:
                errors.append(f"Le critère '{name}' doit avoir une note entre 0 et 20.")
            else:
                criteria_rows.append({'name': name, 'score': crit_score, 'comment': comment})

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            is_new = evaluation is None
            if evaluation is None:
                evaluation = ProjectEvaluation(project=project)
            evaluation.teacher = teacher
            evaluation.score = score
            evaluation.comments = comments
            evaluation.save()

            # Rebuild the rubric to match the submitted rows
            evaluation.criteria.all().delete()
            for order, row in enumerate(criteria_rows):
                EvaluationCriterion.objects.create(
                    evaluation=evaluation,
                    name=row['name'],
                    score=row['score'],
                    comment=row['comment'],
                    order=order,
                )

            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type='status_changed',
                description=(
                    f"Projet noté {score}/20 par {teacher_name}"
                    if is_new else
                    f"Note mise à jour: {score}/20 par {teacher_name}"
                )
            )

            # Optionally validate at the same time (same effects as approve_project)
            if validate_project and project.status == 'submitted':
                project.status = 'validated'
                project.save()

                ProjectActivity.objects.create(
                    project=project,
                    user=request.user,
                    activity_type='status_changed',
                    description=f"Projet validé par {teacher_name}"
                )

                if project.is_assignment_project() and project.project_assignment.assignment_type == 'direct':
                    DirectStudentAssignment.objects.filter(
                        assignment=project.project_assignment,
                        student__in=[member.id for member in project.get_team_members()]
                    ).update(status='validated')

            # Notify the whole team of the grade
            validated_note = " et validé" if (validate_project and project.status == 'validated') else ""
            for member in project.get_team_members():
                Notification.objects.create(
                    recipient=member,
                    project=project,
                    notification_type='project_update',
                    message=(
                        f"Le projet '{project.title}' a été noté{validated_note}: "
                        f"{score}/20 ({evaluation.get_mention()}) par {teacher_name}"
                    )
                )

            messages.success(request, f"Note enregistrée: {score}/20 ({evaluation.get_mention()}).")
            return redirect('teacher:project_review', project_id=project.id)

    # Build the rubric rows shown in the form
    if evaluation:
        existing_criteria = list(evaluation.criteria.all())
    else:
        existing_criteria = []

    if existing_criteria:
        criteria_for_form = [
            {'name': c.name, 'score': c.score, 'comment': c.comment}
            for c in existing_criteria
        ]
    else:
        criteria_for_form = [
            {'name': name, 'score': '', 'comment': ''}
            for name in DEFAULT_EVALUATION_CRITERIA
        ]

    context = {
        'teacher': teacher,
        'project': project,
        'evaluation': evaluation,
        'criteria_for_form': criteria_for_form,
    }

    return render(request, 'teacher/grade_project.html', context)


@login_required
@require_http_methods(["GET"])
def get_module_students(request, module_id):
    """API endpoint to get students for a module"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
        
        # Verify teacher has access to this module
        module_assignment = ModuleAssignment.objects.get(
            teacher=teacher,
            module_id=module_id,
            is_active=True
        )
        module = module_assignment.module
        
        # Get enrolled students
        enrollments = ModuleEnrollment.objects.filter(
            module=module,
            is_active=True
        ).select_related('student__user')
        
        students_data = []
        for enrollment in enrollments:
            student = enrollment.student
            students_data.append({
                'id': student.id,
                'username': student.user.username,
                'full_name': student.user.get_full_name(),
                'student_id': student.student_id,
                'year_display': student.get_year_of_study_display(),
                'initials': (
                    (student.user.first_name[:1] + student.user.last_name[:1])
                    if student.user.first_name and student.user.last_name
                    else student.user.username[:2]
                ).upper()
            })
        
        return JsonResponse({
            'success': True,
            'students': students_data,
            'module': {
                'id': module.id,
                'code': module.code,
                'name': module.name
            }
        })
        
    except (TeacherProfile.DoesNotExist, ModuleAssignment.DoesNotExist):
        return JsonResponse({
            'success': False,
            'error': 'Module non trouvé ou accès non autorisé'
        }, status=403)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)