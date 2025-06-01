from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from .models import TeacherProfile, Module, ModuleAssignment, ModuleEnrollment

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
    pending_projects = teacher_projects.filter(status='submitted').count()
    validated_projects = teacher_projects.filter(status='validated').count()
    
    # Count total students across all modules
    for assignment in assigned_modules:
        total_students += assignment.module.get_enrolled_students_count()
    
    # Get recent modules for display
    recent_modules = assigned_modules[:5]  # Show 5 most recent
    
    context = {
        'teacher': teacher,
        'total_modules': total_modules,
        'total_students': total_students,
        'pending_projects': pending_projects,
        'validated_projects': validated_projects,
        'recent_modules': recent_modules,
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
    deliverables = project.deliverables.all()
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
    
    # Notify student
    Notification.objects.create(
        recipient=project.student,
        project=project,
        notification_type='project_update',
        message=f"Votre projet '{project.title}' a été validé par {teacher.user.get_full_name() or teacher.user.username}"
    )
    
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
    
    # Notify student
    Notification.objects.create(
        recipient=project.student,
        project=project,
        notification_type='project_update',
        message=f"Votre projet '{project.title}' a été rejeté. Consultez les commentaires du projet pour plus de détails."
    )
    
    messages.success(request, f"Projet '{project.title}' rejeté. L'étudiant peut maintenant le modifier et resoumettre.")
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