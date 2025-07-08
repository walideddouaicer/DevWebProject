# teacher/context_processors.py - FIXED version with optimized queries and caching

from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, Count, Sum, Avg
from .models import TeacherProfile, ProjectAssignment, Module, ModuleAssignment


def teacher_context(request):
    """Context processor for teacher-specific data - FIXED VERSION"""
    context = {
        'pending_assignments_count': 0,
        'urgent_deadlines_count': 0,
        'ungraded_projects_count': 0,
        'pending_module_approvals': 0,
        'active_students_count': 0,
        'total_modules_count': 0,
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
        
        # FIXED: Use caching for better performance
        cache_key = f"teacher_context_{teacher.id}_{timezone.now().hour}"
        cached_context = cache.get(cache_key)
        
        if cached_context:
            return cached_context
        
        # Count assignments in various states
        teacher_assignments = ProjectAssignment.objects.filter(teacher=teacher)
        
        context['pending_assignments_count'] = teacher_assignments.filter(
            status='draft'
        ).count()
        
        # FIXED: Enhanced urgent deadlines calculation
        now = timezone.now()
        urgent_count = 0
        
        active_assignments = teacher_assignments.filter(
            status__in=['published', 'in_progress']
        )
        
        for assignment in active_assignments:
            # Check all types of approaching deadlines
            approaching_deadlines = assignment.is_deadline_approaching(days=3)
            if approaching_deadlines:
                urgent_count += len(approaching_deadlines)
        
        context['urgent_deadlines_count'] = urgent_count
        
        # FIXED: Count projects needing grading more efficiently
        from student.models import Project
        ungraded_projects = Project.objects.filter(
            project_assignment__teacher=teacher,
            status='submitted'
        ).count()
        context['ungraded_projects_count'] = ungraded_projects
        
        # Count teacher-created modules pending approval
        pending_modules = Module.objects.filter(
            primary_teacher=teacher,
            created_by_teacher=True,
            requires_approval=True,
            approved_by__isnull=True
        ).count()
        context['pending_module_approvals'] = pending_modules
        
        # FIXED: Count active students across teacher's modules
        teacher_module_ids = ModuleAssignment.objects.filter(
            teacher=teacher,
            is_active=True
        ).values_list('module_id', flat=True)
        
        if teacher_module_ids:
            from teacher.models import ModuleEnrollment
            active_students = ModuleEnrollment.objects.filter(
                module_id__in=teacher_module_ids,
                is_active=True
            ).values('student_id').distinct().count()
            context['active_students_count'] = active_students
        
        # Count total modules assigned to teacher
        context['total_modules_count'] = len(teacher_module_ids)
        
        # Cache for 30 minutes
        cache.set(cache_key, context, 1800)
        
    except TeacherProfile.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in teacher_context processor: {str(e)}")
    
    return context


def teacher_dashboard_stats(request):
    """Enhanced dashboard statistics for teachers - FIXED VERSION"""
    context = {
        'dashboard_stats': {
            'assignments_this_month': 0,
            'projects_submitted_today': 0,
            'average_completion_rate': 0,
            'most_active_module': None,
            'recent_activity_count': 0,
        }
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
        
        # Cache key for dashboard stats
        stats_cache_key = f"teacher_dashboard_stats_{teacher.id}_{timezone.now().date()}"
        cached_stats = cache.get(stats_cache_key)
        
        if cached_stats:
            context['dashboard_stats'] = cached_stats
            return context
        
        now = timezone.now()
        
        # Assignments created this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        context['dashboard_stats']['assignments_this_month'] = ProjectAssignment.objects.filter(
            teacher=teacher,
            created_at__gte=month_start
        ).count()
        
        # Projects submitted today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        
        from student.models import Project
        context['dashboard_stats']['projects_submitted_today'] = Project.objects.filter(
            project_assignment__teacher=teacher,
            assignment_submitted_at__range=(today_start, today_end)
        ).count()
        
        # FIXED: Calculate average completion rate across all assignments
        teacher_assignments = ProjectAssignment.objects.filter(teacher=teacher)
        completion_rates = []
        
        for assignment in teacher_assignments:
            if assignment.status in ['published', 'in_progress', 'completed']:
                completion_rate = assignment.get_completion_percentage()
                completion_rates.append(completion_rate)
        
        if completion_rates:
            context['dashboard_stats']['average_completion_rate'] = int(sum(completion_rates) / len(completion_rates))
        
        # FIXED: Find most active module (by number of projects)
        teacher_modules = ModuleAssignment.objects.filter(
            teacher=teacher,
            is_active=True
        ).select_related('module')
        
        if teacher_modules:
            module_activity = []
            for assignment in teacher_modules:
                module = assignment.module
                project_count = Project.objects.filter(module=module).count()
                student_count = module.get_enrolled_students_count()
                activity_score = project_count + (student_count * 0.5)  # Weight projects more than students
                
                module_activity.append({
                    'module': module,
                    'activity_score': activity_score,
                    'project_count': project_count,
                    'student_count': student_count,
                })
            
            if module_activity:
                most_active = max(module_activity, key=lambda x: x['activity_score'])
                context['dashboard_stats']['most_active_module'] = {
                    'name': most_active['module'].name,
                    'code': most_active['module'].code,
                    'projects': most_active['project_count'],
                    'students': most_active['student_count'],
                }
        
        # Recent activity count (last 7 days)
        week_ago = now - timezone.timedelta(days=7)
        from student.models import ProjectActivity
        
        # Get teacher's modules for activity filtering
        teacher_module_ids = [ta.module_id for ta in teacher_modules]
        
        recent_activity = ProjectActivity.objects.filter(
            project__module_id__in=teacher_module_ids,
            created_at__gte=week_ago
        ).count()
        
        context['dashboard_stats']['recent_activity_count'] = recent_activity
        
        # Cache for 2 hours
        cache.set(stats_cache_key, context['dashboard_stats'], 7200)
        
    except TeacherProfile.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in teacher_dashboard_stats processor: {str(e)}")
    
    return context


def teacher_workload_context(request):
    """Context processor for teacher workload information - OPTIMIZED"""
    context = {
        'workload_stats': {
            'total_assignments': 0,
            'active_assignments': 0,
            'students_taught': 0,
            'pending_reviews': 0,
            'workload_level': 'normal',  # light, normal, heavy, overloaded
        }
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
        
        # Cache workload stats
        workload_cache_key = f"teacher_workload_{teacher.id}_{timezone.now().hour}"
        cached_workload = cache.get(workload_cache_key)
        
        if cached_workload:
            context['workload_stats'] = cached_workload
            return context
        
        # Calculate workload statistics
        teacher_assignments = ProjectAssignment.objects.filter(teacher=teacher)
        
        context['workload_stats']['total_assignments'] = teacher_assignments.count()
        context['workload_stats']['active_assignments'] = teacher_assignments.filter(
            status__in=['published', 'in_progress']
        ).count()
        
        # Calculate total students taught
        teacher_modules = ModuleAssignment.objects.filter(
            teacher=teacher,
            is_active=True
        ).values_list('module_id', flat=True)
        
        if teacher_modules:
            from teacher.models import ModuleEnrollment
            students_taught = ModuleEnrollment.objects.filter(
                module_id__in=teacher_modules,
                is_active=True
            ).values('student_id').distinct().count()
            context['workload_stats']['students_taught'] = students_taught
        
        # Count pending reviews
        from student.models import Project
        pending_reviews = Project.objects.filter(
            project_assignment__teacher=teacher,
            status='submitted'
        ).count()
        context['workload_stats']['pending_reviews'] = pending_reviews
        
        # FIXED: Determine workload level based on multiple factors
        active_assignments = context['workload_stats']['active_assignments']
        students_taught = context['workload_stats']['students_taught']
        pending_reviews = context['workload_stats']['pending_reviews']
        
        # Calculate workload score
        workload_score = (
            active_assignments * 10 +  # Each active assignment adds 10 points
            students_taught * 0.5 +     # Each student adds 0.5 points
            pending_reviews * 5         # Each pending review adds 5 points
        )
        
        if workload_score < 50:
            workload_level = 'light'
        elif workload_score < 150:
            workload_level = 'normal'
        elif workload_score < 300:
            workload_level = 'heavy'
        else:
            workload_level = 'overloaded'
        
        context['workload_stats']['workload_level'] = workload_level
        
        # Cache for 1 hour
        cache.set(workload_cache_key, context['workload_stats'], 3600)
        
    except TeacherProfile.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in teacher_workload_context processor: {str(e)}")
    
    return context


def teacher_notification_context(request):
    """Context processor for teacher-specific notifications and alerts"""
    context = {
        'notifications': {
            'deadline_alerts': [],
            'system_messages': [],
            'student_activity_alerts': [],
        }
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
        
        # Cache notifications
        notif_cache_key = f"teacher_notifications_{teacher.id}_{timezone.now().hour}"
        cached_notifications = cache.get(notif_cache_key)
        
        if cached_notifications:
            context['notifications'] = cached_notifications
            return context
        
        now = timezone.now()
        
        # FIXED: Gather deadline alerts efficiently
        active_assignments = ProjectAssignment.objects.filter(
            teacher=teacher,
            status__in=['published', 'in_progress']
        )
        
        deadline_alerts = []
        for assignment in active_assignments:
            approaching_deadlines = assignment.is_deadline_approaching(days=7)
            
            for deadline_type, days_left in approaching_deadlines:
                deadline_alerts.append({
                    'assignment': assignment,
                    'deadline_type': deadline_type,
                    'days_left': days_left,
                    'urgency': 'high' if days_left <= 1 else 'medium' if days_left <= 3 else 'low'
                })
        
        # Sort by urgency
        deadline_alerts.sort(key=lambda x: (x['days_left'], x['assignment'].title))
        context['notifications']['deadline_alerts'] = deadline_alerts[:5]  # Top 5
        
        # System messages (module approvals, etc.)
        system_messages = []
        
        # Check for pending module approvals
        pending_modules = Module.objects.filter(
            primary_teacher=teacher,
            created_by_teacher=True,
            requires_approval=True,
            approved_by__isnull=True
        )
        
        for module in pending_modules:
            system_messages.append({
                'type': 'module_approval',
                'message': f"Module '{module.code}' en attente d'approbation",
                'module': module,
                'created_at': module.created_at
            })
        
        context['notifications']['system_messages'] = system_messages
        
        # Student activity alerts (high submission volumes, etc.)
        activity_alerts = []
        
        # Check for high submission volumes today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        
        from student.models import Project
        submissions_today = Project.objects.filter(
            project_assignment__teacher=teacher,
            assignment_submitted_at__range=(today_start, today_end)
        ).count()
        
        if submissions_today > 5:  # Threshold for "high volume"
            activity_alerts.append({
                'type': 'high_submissions',
                'message': f"{submissions_today} projets soumis aujourd'hui",
                'count': submissions_today
            })
        
        context['notifications']['student_activity_alerts'] = activity_alerts
        
        # Cache for 30 minutes
        cache.set(notif_cache_key, context['notifications'], 1800)
        
    except TeacherProfile.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in teacher_notification_context processor: {str(e)}")
    
    return context