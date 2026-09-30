# teacher/context_processors.py - FIXED version with optimized queries and caching

from django.core.cache import cache
from django.utils import timezone

from .models import ModuleAssignment, ProjectAssignment, TeacherProfile


def teacher_context(request):
    """Context processor for teacher-specific data - FIXED VERSION"""
    context = {
        "pending_assignments_count": 0,
        "urgent_deadlines_count": 0,
        "ungraded_projects_count": 0,
        "pending_module_approvals": 0,
        "active_students_count": 0,
        "total_modules_count": 0,
    }

    if not request.user.is_authenticated:
        return context

    try:
        teacher = TeacherProfile.objects.get(user=request.user)

        # Use caching for better performance
        cache_key = f"teacher_context_{teacher.id}_{timezone.now().hour}"
        cached_context = cache.get(cache_key)

        if cached_context:
            return cached_context

        # Count assignments in various states
        teacher_assignments = ProjectAssignment.objects.filter(teacher=teacher)

        context["pending_assignments_count"] = teacher_assignments.filter(status="draft").count()

        # Enhanced urgent deadlines calculation
        urgent_count = 0

        active_assignments = teacher_assignments.filter(status__in=["published", "in_progress"])

        for assignment in active_assignments:
            # Check all types of approaching deadlines
            approaching_deadlines = assignment.is_deadline_approaching(days=3)
            if approaching_deadlines:
                urgent_count += len(approaching_deadlines)

        context["urgent_deadlines_count"] = urgent_count

        # Count projects needing grading more efficiently
        from student.models import Project

        ungraded_projects = Project.objects.filter(
            project_assignment__teacher=teacher, status="submitted"
        ).count()
        context["ungraded_projects_count"] = ungraded_projects

        # Module approval system was removed: modules are active immediately,
        # so there is never anything pending approval.
        context["pending_module_approvals"] = 0

        # Count active students across teacher's modules
        teacher_module_ids = ModuleAssignment.objects.filter(
            teacher=teacher, is_active=True
        ).values_list("module_id", flat=True)

        if teacher_module_ids:
            from teacher.models import ModuleEnrollment

            active_students = (
                ModuleEnrollment.objects.filter(module_id__in=teacher_module_ids, is_active=True)
                .values("student_id")
                .distinct()
                .count()
            )
            context["active_students_count"] = active_students

        # Count total modules assigned to teacher
        context["total_modules_count"] = len(teacher_module_ids)

        # Cache for 30 minutes
        cache.set(cache_key, context, 1800)

    except TeacherProfile.DoesNotExist:
        pass
    except Exception:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Error in teacher_context processor")

    return context
