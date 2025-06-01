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
    
    # Get project details
    deliverables = project.deliverables.all()
    milestones = project.milestones.all()
    comments = project.comments.all().select_related('author__user')
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
        # Create comment with teacher flag
        comment = ProjectComment.objects.create(
            project=project,
            author=teacher,  # This links to teacher's StudentProfile equivalent
            content=f"[FEEDBACK ENSEIGNANT]\n{content}"
        )
        
        # Notify student
        Notification.objects.create(
            recipient=project.student,
            project=project,
            notification_type='project_update',
            message=f"Nouveau commentaire de {teacher.user.get_full_name() or teacher.user.username} sur votre projet '{project.title}'"
        )
        
        messages.success(request, "Commentaire ajouté avec succès.")
    else:
        messages.error(request, "Le commentaire ne peut pas être vide.")
    
    return redirect('teacher:project_review', project_id=project.id)