def admin_context(request):
    """Updated context processor (no more pending approvals)"""
    context = {
        'recent_modules_count': 0,  # New: Recent activity instead
        'pending_registrations_count': 0,
        'reported_projects_count': 0,
        'urgent_admin_tasks_count': 0,
    }
    
    if request.user.is_authenticated:
        try:
            from administrator.models import AdminProfile
            admin = AdminProfile.objects.get(user=request.user)
            
            # Count recent modules (last 7 days) instead of pending
            from teacher.models import Module
            from django.utils import timezone
            from datetime import timedelta
            week_ago = timezone.now() - timedelta(days=7)
            recent_modules = Module.objects.filter(
                created_at__gte=week_ago,
                created_by_teacher=True
            ).count()
            context['recent_modules_count'] = recent_modules
            # Rest of your existing context... (all zeros for now)
        except:
            pass
    
    return context 