def admin_context(request):
    """Context processor for administrator-specific data"""
    context = {
        'pending_module_approvals_count': 0,
        'pending_registrations_count': 0,
        'reported_projects_count': 0,
        'urgent_admin_tasks_count': 0,
    }
    
    if request.user.is_authenticated:
        try:
            from administrator.models import AdminProfile
            admin = AdminProfile.objects.get(user=request.user)
            
            # Count teacher-created modules pending approval
            from teacher.models import Module
            pending_modules = Module.objects.filter(
                created_by_teacher=True,
                requires_approval=True,
                approved_by__isnull=True
            ).count()
            context['pending_module_approvals_count'] = pending_modules
            
            # Count pending registrations
            try:
                from accounts.models import PendingRegistration
                pending_registrations = PendingRegistration.objects.filter(
                    is_approved=False
                ).count()
                context['pending_registrations_count'] = pending_registrations
            except ImportError:
                pass
            
            # Count reported projects
            from student.models import Project
            reported_projects = Project.objects.filter(
                is_reported=True,
                is_hidden_by_admin=False
            ).count()
            context['reported_projects_count'] = reported_projects
            
            # Calculate urgent tasks
            urgent_tasks = (
                context['pending_module_approvals_count'] + 
                context['pending_registrations_count'] + 
                context['reported_projects_count']
            )
            context['urgent_admin_tasks_count'] = urgent_tasks
            
        except:
            # If AdminProfile doesn't exist or other issues
            pass
    
    return context 