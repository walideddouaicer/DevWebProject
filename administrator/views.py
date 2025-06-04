# administrator/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta

# Import models from other apps
from .models import AdminProfile
from teacher.models import TeacherProfile, Module, ModuleAssignment, ModuleEnrollment
from student.models import StudentProfile, Project, ProjectActivity

# Authentication decorator for administrators
def admin_required(view_func):
    """Decorator to ensure user is an administrator"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        try:
            AdminProfile.objects.get(user=request.user)
        except AdminProfile.DoesNotExist:
            messages.error(request, "Vous n'avez pas les droits d'administrateur.")
            return redirect('login')
        
        return view_func(request, *args, **kwargs)
    return wrapper

@admin_required
def dashboard(request):
    """Administrator dashboard with key statistics - FIXED VERSION"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    # Basic statistics - these work correctly
    total_projects = Project.objects.count()
    total_students = StudentProfile.objects.count()
    total_teachers = TeacherProfile.objects.count()
    total_modules = Module.objects.filter(is_active=True).count()
    
    # Project status breakdown - calculate manually for accuracy
    projects_in_progress = Project.objects.filter(status='in_progress').count()
    projects_submitted = Project.objects.filter(status='submitted').count()
    projects_validated = Project.objects.filter(status='validated').count()
    projects_rejected = Project.objects.filter(status='rejected').count()
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_projects = Project.objects.filter(created_at__gte=thirty_days_ago).count()
    recent_enrollments = ModuleEnrollment.objects.filter(enrolled_at__gte=thirty_days_ago).count()
    
    # FIXED: Module statistics with manual counting (this is what works!)
    modules_with_stats = []
    
    for module in Module.objects.filter(is_active=True).order_by('code'):
        # Manual count for each module - this is the pattern that works
        student_count = ModuleEnrollment.objects.filter(
            module=module, 
            is_active=True
        ).count()
        
        teacher_count = ModuleAssignment.objects.filter(
            module=module, 
            is_active=True
        ).count()
        
        project_count = Project.objects.filter(module=module).count()
        
        # Create a module dict with stats
        module_data = {
            'id': module.id,
            'code': module.code,
            'name': module.name,
            'academic_year': module.academic_year,
            'semester': module.semester,
            'get_semester_display': module.get_semester_display(),
            'student_count': student_count,
            'teacher_count': teacher_count,
            'project_count': project_count,
        }
        
        modules_with_stats.append(module_data)
    
    # Sort by student count (descending) and take top 5
    modules_with_stats.sort(key=lambda x: x['student_count'], reverse=True)
    modules_with_stats = modules_with_stats[:5]
    
    # Recent projects for activity feed
    latest_projects = Project.objects.select_related(
        'student__user', 'module'
    ).order_by('-updated_at')[:10]
    
    context = {
        'admin': admin,
        'total_projects': total_projects,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_modules': total_modules,
        'projects_in_progress': projects_in_progress,
        'projects_submitted': projects_submitted,
        'projects_validated': projects_validated,
        'projects_rejected': projects_rejected,
        'recent_projects': recent_projects,
        'recent_enrollments': recent_enrollments,
        'modules_with_stats': modules_with_stats,  # This works because of manual calculation
        'latest_projects': latest_projects,
    }
    
    return render(request, 'administrator/dashboard.html', context)

@admin_required
def projects_list(request):
    """List all projects with filtering capabilities - FIXED VERSION"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    # Start with all projects
    projects = Project.objects.select_related(
        'student__user', 'module'
    ).prefetch_related('collaborators__user')
    
    # Apply filters (existing filter logic...)
    search_query = request.GET.get('search', '')
    if search_query:
        projects = projects.filter(
            Q(title__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query) |
            Q(student__user__username__icontains=search_query)
        )
    
    # Filter by module
    module_id = request.GET.get('module')
    if module_id:
        projects = projects.filter(module_id=module_id)
    
    # Filter by teacher (through module assignments)
    teacher_id = request.GET.get('teacher')
    if teacher_id:
        teacher_modules = ModuleAssignment.objects.filter(
            teacher_id=teacher_id, is_active=True
        ).values_list('module_id', flat=True)
        projects = projects.filter(module_id__in=teacher_modules)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        projects = projects.filter(status=status)
    
    # Filter by project type
    project_type = request.GET.get('project_type')
    if project_type:
        projects = projects.filter(project_type=project_type)
    
    # Filter by academic year
    academic_year = request.GET.get('academic_year')
    if academic_year:
        projects = projects.filter(module__academic_year=academic_year)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        projects = projects.filter(created_at__gte=date_from)
    if date_to:
        projects = projects.filter(created_at__lte=date_to)
    
    # Order by latest first
    projects = projects.order_by('-updated_at')
    
    # FIXED: Calculate statistics manually
    total_projects = projects.count()
    submitted_count = projects.filter(status='submitted').count()
    validated_count = projects.filter(status='validated').count()
    rejected_count = projects.filter(status='rejected').count()
    in_progress_count = projects.filter(status='in_progress').count()
    
    # Pagination
    paginator = Paginator(projects, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    modules = Module.objects.filter(is_active=True).order_by('code')
    teachers = TeacherProfile.objects.select_related('user').order_by('user__first_name')
    academic_years = Module.objects.values_list('academic_year', flat=True).distinct().order_by('academic_year')
    
    context = {
        'admin': admin,
        'page_obj': page_obj,
        'modules': modules,
        'teachers': teachers,
        'academic_years': academic_years,
        'search_query': search_query,
        'project_types': Project.PROJECT_TYPES,
        'status_choices': Project.STATUS_CHOICES,
        # FIXED: Add manually calculated counts
        'total_projects': total_projects,
        'submitted_count': submitted_count,
        'validated_count': validated_count,
        'rejected_count': rejected_count,
        'in_progress_count': in_progress_count,
        'selected_module': module_id,
        'selected_teacher': teacher_id,
        'selected_status': status,
        'selected_project_type': project_type,
        'selected_academic_year': academic_year,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'administrator/projects_list.html', context)

@admin_required
def project_detail(request, project_id):
    """View detailed information about a specific project (read-only)"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    project = get_object_or_404(
        Project.objects.select_related('student__user', 'module'),
        id=project_id
    )
    
    # Get project details
    deliverables = project.deliverables.all().order_by('-upload_date')
    milestones = project.milestones.all().order_by('due_date')
    comments = project.comments.all().select_related('author').order_by('-created_at')
    activities = project.activities.all().select_related('user').order_by('-created_at')
    collaborators = project.collaborators.all().select_related('user')
    
    # Get assigned teachers for this project's module
    assigned_teachers = []
    if project.module:
        assignments = ModuleAssignment.objects.filter(
            module=project.module,
            is_active=True
        ).select_related('teacher__user')
        assigned_teachers = [assignment.teacher for assignment in assignments]
    
    context = {
        'admin': admin,
        'project': project,
        'deliverables': deliverables,
        'milestones': milestones,
        'comments': comments,
        'activities': activities,
        'collaborators': collaborators,
        'assigned_teachers': assigned_teachers,
    }
    
    return render(request, 'administrator/project_detail.html', context)

@admin_required
def modules_list(request):
    """List all modules with management options - FIXED VERSION"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    # Get base queryset
    modules = Module.objects.all().order_by('-created_at')
    
    # Apply filters
    search_query = request.GET.get('search', '')
    if search_query:
        modules = modules.filter(
            Q(code__icontains=search_query) |
            Q(name__icontains=search_query)
        )
    
    academic_year = request.GET.get('academic_year')
    if academic_year:
        modules = modules.filter(academic_year=academic_year)
    
    semester = request.GET.get('semester')
    if semester:
        modules = modules.filter(semester=semester)
    
    # FIXED: Calculate totals manually for accuracy
    total_modules = modules.count()
    active_modules = modules.filter(is_active=True).count()
    
    # Calculate total students and teachers across all modules
    total_students_enrolled = 0
    total_teachers_assigned = 0
    
    for module in modules:
        total_students_enrolled += ModuleEnrollment.objects.filter(
            module=module, is_active=True
        ).count()
        total_teachers_assigned += ModuleAssignment.objects.filter(
            module=module, is_active=True
        ).count()
    
    # FIXED: Add manual counts to each module for template use
    modules_with_counts = []
    for module in modules:
        student_count = ModuleEnrollment.objects.filter(
            module=module, is_active=True
        ).count()
        teacher_count = ModuleAssignment.objects.filter(
            module=module, is_active=True
        ).count()
        project_count = Project.objects.filter(module=module).count()
        
        # Add counts as attributes
        module.student_count = student_count
        module.teacher_count = teacher_count  
        module.project_count = project_count
        
        modules_with_counts.append(module)
    
    # Get filter options
    academic_years = Module.objects.values_list('academic_year', flat=True).distinct().order_by('academic_year')
    
    context = {
        'admin': admin,
        'modules': modules_with_counts,  # Now has count attributes
        'academic_years': academic_years,
        'search_query': search_query,
        'selected_academic_year': academic_year,
        'selected_semester': semester,
        'semester_choices': Module._meta.get_field('semester').choices,
        # FIXED: Add totals calculated manually
        'total_modules': total_modules,
        'active_modules': active_modules,
        'total_students_enrolled': total_students_enrolled,
        'total_teachers_assigned': total_teachers_assigned,
    }
    
    return render(request, 'administrator/modules_list.html', context)

@admin_required
def module_create(request):
    """Create a new module"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        code = request.POST.get('code')
        description = request.POST.get('description', '')
        academic_year = request.POST.get('academic_year')
        semester = request.POST.get('semester')
        
        # Validate required fields
        if not all([name, code, academic_year, semester]):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
            return render(request, 'administrator/module_create.html', {'admin': admin})
        
        # Check if module code already exists
        if Module.objects.filter(code=code).exists():
            messages.error(request, f"Un module avec le code '{code}' existe déjà.")
            return render(request, 'administrator/module_create.html', {'admin': admin})
        
        # Create the module
        try:
            module = Module.objects.create(
                name=name,
                code=code.upper(),
                description=description,
                academic_year=academic_year,
                semester=semester,
                is_active=True
            )
            
            messages.success(request, f"Module '{module.code} - {module.name}' créé avec succès.")
            return redirect('administrator:module_detail', module_id=module.id)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la création du module: {str(e)}")
    
    context = {
        'admin': admin,
        'semester_choices': Module._meta.get_field('semester').choices,
    }
    
    return render(request, 'administrator/module_create.html', context)

@admin_required
def module_detail(request, module_id):
    """View detailed information about a module"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    module = get_object_or_404(Module, id=module_id)
    
    # Get module statistics
    enrollments = ModuleEnrollment.objects.filter(
        module=module, is_active=True
    ).select_related('student__user')
    
    assignments = ModuleAssignment.objects.filter(
        module=module, is_active=True
    ).select_related('teacher__user')
    
    module_projects = Project.objects.filter(module=module).select_related('student__user')
    
    context = {
        'admin': admin,
        'module': module,
        'enrollments': enrollments,
        'assignments': assignments,
        'module_projects': module_projects,
        'total_students': enrollments.count(),
        'total_teachers': assignments.count(),
        'total_projects': module_projects.count(),
    }
    
    return render(request, 'administrator/module_detail.html', context)

@admin_required
def module_edit(request, module_id):
    """Edit module information"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    module = get_object_or_404(Module, id=module_id)
    
    if request.method == 'POST':
        # Update module fields
        module.name = request.POST.get('name', module.name)
        module.description = request.POST.get('description', module.description)
        module.academic_year = request.POST.get('academic_year', module.academic_year)
        module.semester = request.POST.get('semester', module.semester)
        module.is_active = request.POST.get('is_active') == 'on'
        
        try:
            module.save()
            messages.success(request, f"Module '{module.code}' mis à jour avec succès.")
            return redirect('administrator:module_detail', module_id=module.id)
        except Exception as e:
            messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")
    
    context = {
        'admin': admin,
        'module': module,
        'semester_choices': Module._meta.get_field('semester').choices,
    }
    
    return render(request, 'administrator/module_edit.html', context)

@admin_required
def module_delete(request, module_id):
    """Delete a module (soft delete - set is_active to False)"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    module = get_object_or_404(Module, id=module_id)
    
    if request.method == 'POST':
        # Soft delete - set is_active to False
        module.is_active = False
        module.save()
        
        messages.success(request, f"Module '{module.code}' désactivé avec succès.")
        return redirect('administrator:modules_list')
    
    # Get statistics for confirmation
    student_count = ModuleEnrollment.objects.filter(module=module, is_active=True).count()
    teacher_count = ModuleAssignment.objects.filter(module=module, is_active=True).count()
    project_count = Project.objects.filter(module=module).count()
    
    context = {
        'admin': admin,
        'module': module,
        'student_count': student_count,
        'teacher_count': teacher_count,
        'project_count': project_count,
    }
    
    return render(request, 'administrator/module_delete.html', context)

@admin_required
def assignments_management(request):
    """Manage teacher-module assignments - FIXED VERSION"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    # Get all active assignments
    assignments = ModuleAssignment.objects.filter(
        is_active=True
    ).select_related('teacher__user', 'module').order_by('module__code')
    
    # Get teachers and modules for new assignments
    teachers = TeacherProfile.objects.select_related('user').order_by('user__first_name')
    modules = Module.objects.filter(is_active=True).order_by('code')
    
    # FIXED: Calculate unassigned modules manually
    assigned_module_ids = assignments.values_list('module_id', flat=True)
    unassigned_modules = modules.exclude(id__in=assigned_module_ids)
    
    # FIXED: Calculate statistics manually for accuracy
    total_assignments = assignments.count()
    total_teachers = teachers.count()
    total_modules = modules.count()
    total_unassigned = unassigned_modules.count()
    
    # FIXED: Add workload counts to teachers for template
    teachers_with_workload = []
    for teacher in teachers:
        teacher_assignments = ModuleAssignment.objects.filter(
            teacher=teacher, is_active=True
        ).count()
        
        # Calculate total students taught by this teacher
        teacher_modules = ModuleAssignment.objects.filter(
            teacher=teacher, is_active=True
        ).values_list('module_id', flat=True)
        
        total_students = 0
        for module_id in teacher_modules:
            total_students += ModuleEnrollment.objects.filter(
                module_id=module_id, is_active=True
            ).count()
        
        # Add attributes for template
        teacher.assignment_count = teacher_assignments
        teacher.student_count = total_students
        
        teachers_with_workload.append(teacher)
    
    context = {
        'admin': admin,
        'assignments': assignments,
        'teachers': teachers_with_workload,  # Now includes workload data
        'modules': modules,
        'unassigned_modules': unassigned_modules,
        # FIXED: Add manual counts
        'total_assignments': total_assignments,
        'total_teachers': total_teachers,
        'total_modules': total_modules,
        'total_unassigned': total_unassigned,
    }
    
    return render(request, 'administrator/assignments_management.html', context)

@admin_required
def assign_teacher_to_module(request):
    """Assign a teacher to a module"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    if request.method == 'POST':
        teacher_id = request.POST.get('teacher_id')
        module_id = request.POST.get('module_id')
        
        if not teacher_id or not module_id:
            messages.error(request, "Veuillez sélectionner un enseignant et un module.")
            return redirect('administrator:assignments_management')
        
        try:
            teacher = TeacherProfile.objects.get(id=teacher_id)
            module = Module.objects.get(id=module_id)
            
            # Check if assignment already exists
            existing_assignment = ModuleAssignment.objects.filter(
                teacher=teacher, module=module
            ).first()
            
            if existing_assignment:
                if existing_assignment.is_active:
                    messages.info(request, f"{teacher.user.get_full_name()} est déjà assigné au module {module.code}.")
                else:
                    # Reactivate existing assignment
                    existing_assignment.is_active = True
                    existing_assignment.assigned_by = request.user
                    existing_assignment.save()
                    messages.success(request, f"{teacher.user.get_full_name()} a été réassigné au module {module.code}.")
            else:
                # Create new assignment
                ModuleAssignment.objects.create(
                    teacher=teacher,
                    module=module,
                    assigned_by=request.user,
                    is_active=True
                )
                messages.success(request, f"{teacher.user.get_full_name()} a été assigné au module {module.code}.")
                
        except (TeacherProfile.DoesNotExist, Module.DoesNotExist) as e:
            messages.error(request, "Enseignant ou module introuvable.")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'assignation: {str(e)}")
    
    return redirect('administrator:assignments_management')

@admin_required
def remove_assignment(request, assignment_id):
    """Remove a teacher-module assignment"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    try:
        assignment = ModuleAssignment.objects.get(id=assignment_id, is_active=True)
        assignment.is_active = False
        assignment.save()
        
        messages.success(request, f"Assignation de {assignment.teacher.user.get_full_name()} au module {assignment.module.code} supprimée.")
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Assignation introuvable.")
    except Exception as e:
        messages.error(request, f"Erreur lors de la suppression: {str(e)}")
    
    return redirect('administrator:assignments_management')

@admin_required
def users_overview(request):
    """Overview of all users in the system"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    # User statistics
    total_students = StudentProfile.objects.count()
    total_teachers = TeacherProfile.objects.count()
    total_admins = AdminProfile.objects.count()
    
    # Recent registrations (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_students = StudentProfile.objects.filter(user__date_joined__gte=thirty_days_ago).count()
    recent_teachers = TeacherProfile.objects.filter(user__date_joined__gte=thirty_days_ago).count()
    
    context = {
        'admin': admin,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_admins': total_admins,
        'recent_students': recent_students,
        'recent_teachers': recent_teachers,
    }
    
    return render(request, 'administrator/users_overview.html', context)

@admin_required
def students_list(request):
    """List all students"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    students = StudentProfile.objects.select_related('user').order_by('user__first_name')
    
    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(student_id__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(students, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'admin': admin,
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'administrator/students_list.html', context)

@admin_required
def teachers_list(request):
    """List all teachers"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    teachers = TeacherProfile.objects.select_related('user').order_by('user__first_name')
    
    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        teachers = teachers.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(teacher_id__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(teachers, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'admin': admin,
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'administrator/teachers_list.html', context)

@admin_required
def statistics(request):
    """Detailed statistics page"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    # Project statistics by type
    project_type_stats = []
    for type_key, type_name in Project.PROJECT_TYPES:
        count = Project.objects.filter(project_type=type_key).count()
        project_type_stats.append({'type': type_name, 'count': count})
    
    # Project statistics by status
    status_stats = []
    for status_key, status_name in Project.STATUS_CHOICES:
        count = Project.objects.filter(status=status_key).count()
        status_stats.append({'status': status_name, 'count': count})
    
    # Module statistics
    module_stats = Module.objects.filter(is_active=True).annotate(
        student_count=Count('enrollments', filter=Q(enrollments__is_active=True)),
        project_count=Count('projects')
    ).order_by('-student_count')
    
    # Teacher workload
    teacher_workload = TeacherProfile.objects.annotate(
        module_count=Count('module_assignments', filter=Q(module_assignments__is_active=True)),
        student_count=Count('module_assignments__module__enrollments', 
                          filter=Q(module_assignments__is_active=True, 
                                  module_assignments__module__enrollments__is_active=True))
    ).order_by('-module_count')
    
    context = {
        'admin': admin,
        'project_type_stats': project_type_stats,
        'status_stats': status_stats,
        'module_stats': module_stats,
        'teacher_workload': teacher_workload,
    }
    
    return render(request, 'administrator/statistics.html', context)

@admin_required
def remove_student_from_module(request, module_id, student_id):
    """Remove a student from a module"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    try:
        module = Module.objects.get(id=module_id)
        student = StudentProfile.objects.get(id=student_id)
        
        # Find the enrollment
        enrollment = ModuleEnrollment.objects.get(
            module=module,
            student=student,
            is_active=True
        )
        
        # Deactivate the enrollment (soft delete)
        enrollment.is_active = False
        enrollment.save()
        
        if request.method == 'POST':
            # For AJAX requests
            return JsonResponse({
                'success': True, 
                'message': f'{student.user.get_full_name() or student.user.username} a été désinscrit du module {module.code}.'
            })
        else:
            # For regular requests
            messages.success(request, f'{student.user.get_full_name() or student.user.username} a été désinscrit du module {module.code}.')
            return redirect('administrator:module_detail', module_id=module.id)
            
    except ModuleEnrollment.DoesNotExist:
        error_msg = "Cet étudiant n'est pas inscrit à ce module."
        if request.method == 'POST':
            return JsonResponse({'success': False, 'message': error_msg})
        else:
            messages.error(request, error_msg)
            return redirect('administrator:module_detail', module_id=module_id)
    except (Module.DoesNotExist, StudentProfile.DoesNotExist):
        error_msg = "Module ou étudiant introuvable."
        if request.method == 'POST':
            return JsonResponse({'success': False, 'message': error_msg})
        else:
            messages.error(request, error_msg)
            return redirect('administrator:modules_list')
    except Exception as e:
        error_msg = f"Erreur lors de la désinscription: {str(e)}"
        if request.method == 'POST':
            return JsonResponse({'success': False, 'message': error_msg})
        else:
            messages.error(request, error_msg)
            return redirect('administrator:module_detail', module_id=module_id)

@admin_required
def exports(request):
    """Export options page"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    
    context = {
        'admin': admin,
    }
    
    return render(request, 'administrator/exports.html', context)

@admin_required
def export_projects(request):
    """Export projects to Excel"""
    # This is a placeholder - we'll implement this in Phase 5
    messages.info(request, "Fonctionnalité d'export en cours de développement.")
    return redirect('administrator:exports')

@admin_required
def export_statistics(request):
    """Export statistics to Excel"""
    # This is a placeholder - we'll implement this in Phase 5
    messages.info(request, "Fonctionnalité d'export en cours de développement.")
    return redirect('administrator:exports')