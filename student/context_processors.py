# student/context_processors.py - Fixed version with optimized queries and better error handling

from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, Count, Exists, OuterRef
from .models import StudentProfile, CollaborationInvitation, Notification
from teacher.models import ProjectAssignment, DirectStudentAssignment, Module


def student_context(request):
    """Enhanced context processor for invitations, notifications, and assignments - TEAM-BASED VERSION"""
    context = {
        'invitation_count': 0,
        'unread_notifications_count': 0,
        'urgent_assignments_count': 0,
        'overdue_assignments_count': 0,
        'pending_assignments_count': 0,
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        student = StudentProfile.objects.get(user=request.user)
        
        # Use a cache key based on user ID and timestamp for better performance
        cache_key = f"student_context_{student.id}_{timezone.now().hour}"
        cached_context = cache.get(cache_key)
        
        if cached_context:
            return cached_context
        
        # Collaboration invitation count (project collaborations)
        context['invitation_count'] = CollaborationInvitation.objects.filter(
            recipient=student,
            status='pending'
        ).count()
        
        # Unread notifications count
        context['unread_notifications_count'] = Notification.objects.filter(
            recipient=student,
            is_read=False
        ).count()
        
        # ENHANCED: Assignment-related counts with optimized queries
        now = timezone.now()
        
        # Get student's enrolled modules efficiently
        enrolled_module_ids = list(student.module_enrollments.filter(
            is_active=True
        ).values_list('module_id', flat=True))
        
        if enrolled_module_ids:
            # Get all active assignments from enrolled modules
            active_assignments = ProjectAssignment.objects.filter(
                module_id__in=enrolled_module_ids,
                status__in=['published', 'in_progress']
            ).select_related('module')
            
            urgent_count = 0
            overdue_count = 0
            pending_count = 0
            
            # Get direct assignments for this student
            student_direct_assignments = DirectStudentAssignment.objects.filter(
                student=student,
                assignment__in=active_assignments
            ).select_related('assignment')
            
            # UPDATED: Get projects this student is working on (instead of groups)
            from .models import Project
            student_assignment_projects = Project.objects.filter(
                Q(student=student) | Q(collaborators=student),
                project_assignment__in=active_assignments
            ).select_related('project_assignment')
            
            # Create a set of assignments the student is already working on
            working_assignments = set(p.project_assignment.id for p in student_assignment_projects)
            
            # Process direct assignments
            for direct_assignment in student_direct_assignments:
                assignment = direct_assignment.assignment
                
                # Check if project already created/submitted
                has_submitted = assignment.id in working_assignments
                
                if not has_submitted:
                    pending_count += 1
                    
                    # Check for overdue
                    if direct_assignment.is_overdue():
                        overdue_count += 1
                    else:
                        # Check for urgent deadlines
                        approaching_deadlines = assignment.is_deadline_approaching(days=7)
                        if approaching_deadlines:
                            urgent_count += 1
            
            # UPDATED: Process choice-based assignments (team-based approach)
            for assignment in active_assignments.filter(assignment_type='choice_based'):
                # Check if student is working on this assignment
                has_project = assignment.id in working_assignments
                
                if not has_project:
                    pending_count += 1
                    
                    # Check for urgent deadlines based on assignment deadlines
                    urgent_deadlines = []
                    
                    if assignment.selection_deadline:
                        days_left = (assignment.selection_deadline - now).days
                        if assignment.selection_deadline < now:
                            overdue_count += 1
                            continue
                        elif days_left <= 3:
                            urgent_deadlines.append(('selection', days_left))
                    
                    if assignment.deadline:
                        days_left = (assignment.deadline - now).days
                        if assignment.deadline < now:
                            overdue_count += 1
                            continue
                        elif days_left <= 7:
                            urgent_deadlines.append(('final', days_left))
                    
                    if urgent_deadlines:
                        urgent_count += 1
            
            context.update({
                'urgent_assignments_count': urgent_count,
                'overdue_assignments_count': overdue_count,
                'pending_assignments_count': pending_count,
            })
        
        # Cache the result for better performance (cache for 30 minutes)
        cache.set(cache_key, context, 1800)
        
    except StudentProfile.DoesNotExist:
        # Return default context if student profile doesn't exist
        pass
    except Exception as e:
        # Log the error but don't break the page
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in student_context processor: {str(e)}")
    
    return context


def student_navigation_context(request):
    """Additional context for student navigation - UPDATED FOR TEAMS"""
    context = {
        'has_active_projects': False,
        'has_pending_invitations': False,
        'has_urgent_tasks': False,
        'current_semester_modules': [],
        'total_projects_count': 0,
        'assignment_projects_count': 0,
        'personal_projects_count': 0,
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        student = StudentProfile.objects.get(user=request.user)
        
        # Cache key for navigation context
        nav_cache_key = f"student_nav_{student.id}_{timezone.now().hour}"
        cached_nav_context = cache.get(nav_cache_key)
        
        if cached_nav_context:
            return cached_nav_context
        
        # Check for active projects
        from .models import Project
        context['has_active_projects'] = Project.objects.filter(
            Q(student=student) | Q(collaborators=student),
            status='in_progress'
        ).exists()
        
        # Check for pending invitations
        context['has_pending_invitations'] = CollaborationInvitation.objects.filter(
            recipient=student,
            status='pending'
        ).exists()
        
        # Check for urgent tasks (from main context)
        main_context = student_context(request)
        context['has_urgent_tasks'] = (
            main_context['urgent_assignments_count'] > 0 or
            main_context['overdue_assignments_count'] > 0
        )
        
        # Get current semester modules
        current_year = timezone.now().year
        current_month = timezone.now().month
        
        # Determine current semester (approximate)
        if 9 <= current_month <= 12:  # September to December
            current_semester = 'S1'
            academic_year = f"{current_year}-{current_year + 1}"
        elif 1 <= current_month <= 6:  # January to June
            current_semester = 'S2'
            academic_year = f"{current_year - 1}-{current_year}"
        else:  # Summer
            current_semester = 'Summer'
            academic_year = f"{current_year}-{current_year + 1}"
        
        context['current_semester_modules'] = Module.objects.filter(
            enrollments__student=student,
            enrollments__is_active=True,
            academic_year=academic_year,
            semester=current_semester,
            is_active=True
        ).distinct()[:5]  # Limit to 5 for navigation
        
        # ENHANCED: Project counts with assignment breakdown
        all_projects = Project.objects.filter(
            Q(student=student) | Q(collaborators=student)
        ).distinct()
        
        context['total_projects_count'] = all_projects.count()
        context['assignment_projects_count'] = all_projects.filter(
            assignment_source='teacher_assigned'
        ).count()
        context['personal_projects_count'] = all_projects.filter(
            assignment_source='student_initiated'
        ).count()
        
        # Cache for 1 hour
        cache.set(nav_cache_key, context, 3600)
        
    except StudentProfile.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in student_navigation_context processor: {str(e)}")
    
    return context


def student_dashboard_stats(request):
    """Context processor for dashboard statistics - TEAM-BASED VERSION"""
    context = {
        'dashboard_stats': {
            'projects_this_month': 0,
            'assignments_due_soon': 0,
            'collaboration_requests': 0,
            'completion_rate': 0,
            'team_projects_count': 0,
            'individual_projects_count': 0,
        }
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        student = StudentProfile.objects.get(user=request.user)
        
        # Cache key for dashboard stats
        stats_cache_key = f"student_dashboard_stats_{student.id}_{timezone.now().date()}"
        cached_stats = cache.get(stats_cache_key)
        
        if cached_stats:
            context['dashboard_stats'] = cached_stats
            return context
        
        # Calculate dashboard statistics
        from .models import Project
        now = timezone.now()
        
        # Projects created this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        all_projects = Project.objects.filter(
            Q(student=student) | Q(collaborators=student),
            created_at__gte=month_start
        ).distinct()
        context['dashboard_stats']['projects_this_month'] = all_projects.count()
        
        # Assignments due soon (next 7 days)
        next_week = now + timezone.timedelta(days=7)
        
        # Get enrolled modules
        enrolled_modules = student.module_enrollments.filter(
            is_active=True
        ).values_list('module_id', flat=True)
        
        due_soon_count = ProjectAssignment.objects.filter(
            module_id__in=enrolled_modules,
            status='published',
            deadline__range=(now, next_week)
        ).count()
        
        context['dashboard_stats']['assignments_due_soon'] = due_soon_count
        
        # Collaboration requests (pending invitations)
        context['dashboard_stats']['collaboration_requests'] = CollaborationInvitation.objects.filter(
            recipient=student,
            status='pending'
        ).count()
        
        # ENHANCED: Team vs individual project breakdown
        student_projects = Project.objects.filter(
            Q(student=student) | Q(collaborators=student)
        ).distinct()
        
        team_projects = student_projects.filter(collaborators__isnull=False).distinct().count()
        individual_projects = student_projects.filter(collaborators__isnull=True).count()
        
        context['dashboard_stats']['team_projects_count'] = team_projects
        context['dashboard_stats']['individual_projects_count'] = individual_projects
        
        # Completion rate (validated projects / total projects)
        total_projects = student_projects.count()
        
        if total_projects > 0:
            validated_projects = student_projects.filter(
                status='validated'
            ).count()
            context['dashboard_stats']['completion_rate'] = int((validated_projects / total_projects) * 100)
        
        # Cache for 4 hours
        cache.set(stats_cache_key, context['dashboard_stats'], 14400)
        
    except StudentProfile.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in student_dashboard_stats processor: {str(e)}")
    
    return context


def student_assignment_context(request):
    """NEW: Context processor specifically for assignment-related data"""
    context = {
        'assignment_stats': {
            'active_assignments': 0,
            'completed_assignments': 0,
            'team_assignments': 0,
            'individual_assignments': 0,
            'overdue_assignments': 0,
        }
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        student = StudentProfile.objects.get(user=request.user)
        
        # Cache key for assignment stats
        assignment_cache_key = f"student_assignment_stats_{student.id}_{timezone.now().date()}"
        cached_stats = cache.get(assignment_cache_key)
        
        if cached_stats:
            context['assignment_stats'] = cached_stats
            return context
        
        # Get enrolled modules
        enrolled_modules = student.module_enrollments.filter(
            is_active=True
        ).values_list('module_id', flat=True)
        
        if enrolled_modules:
            # Get all assignments from enrolled modules
            all_assignments = ProjectAssignment.objects.filter(
                module_id__in=enrolled_modules,
                status__in=['published', 'in_progress']
            )
            
            # Get student's assignment projects
            from .models import Project
            student_assignment_projects = Project.objects.filter(
                Q(student=student) | Q(collaborators=student),
                project_assignment__in=all_assignments
            ).select_related('project_assignment')
            
            # Calculate assignment statistics
            context['assignment_stats']['active_assignments'] = all_assignments.count()
            context['assignment_stats']['completed_assignments'] = student_assignment_projects.filter(
                status='validated'
            ).count()
            
            # Count team vs individual assignments
            team_assignments = student_assignment_projects.filter(
                project_assignment__is_team_work=True
            ).count()
            individual_assignments = student_assignment_projects.filter(
                project_assignment__is_team_work=False
            ).count()
            
            context['assignment_stats']['team_assignments'] = team_assignments
            context['assignment_stats']['individual_assignments'] = individual_assignments
            
            # Count overdue assignments
            now = timezone.now()
            overdue_count = 0
            
            for assignment in all_assignments:
                # Check if student has project for this assignment
                has_project = student_assignment_projects.filter(
                    project_assignment=assignment
                ).exists()
                
                if not has_project and assignment.deadline < now:
                    overdue_count += 1
            
            context['assignment_stats']['overdue_assignments'] = overdue_count
        
        # Cache for 2 hours
        cache.set(assignment_cache_key, context['assignment_stats'], 7200)
        
    except StudentProfile.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in student_assignment_context processor: {str(e)}")
    
    return context