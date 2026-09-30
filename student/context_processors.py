# student/context_processors.py - Fixed version with optimized queries and better error handling

from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from teacher.models import DirectStudentAssignment, ProjectAssignment

from .models import CollaborationInvitation, Notification, StudentProfile


def student_context(request):
    """Enhanced context processor for invitations, notifications, and assignments - TEAM-BASED VERSION"""
    context = {
        "invitation_count": 0,
        "unread_notifications_count": 0,
        "urgent_assignments_count": 0,
        "overdue_assignments_count": 0,
        "pending_assignments_count": 0,
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
        context["invitation_count"] = CollaborationInvitation.objects.filter(
            recipient=student, status="pending"
        ).count()

        # Unread notifications count
        context["unread_notifications_count"] = Notification.objects.filter(
            recipient=student, is_read=False
        ).count()

        # Assignment-related counts with optimized queries
        now = timezone.now()

        # Get student's enrolled modules efficiently
        enrolled_module_ids = list(
            student.module_enrollments.filter(is_active=True).values_list("module_id", flat=True)
        )

        if enrolled_module_ids:
            # Get all active assignments from enrolled modules
            active_assignments = ProjectAssignment.objects.filter(
                module_id__in=enrolled_module_ids, status__in=["published", "in_progress"]
            ).select_related("module")

            urgent_count = 0
            overdue_count = 0
            pending_count = 0

            # Get direct assignments for this student
            student_direct_assignments = DirectStudentAssignment.objects.filter(
                student=student, assignment__in=active_assignments
            ).select_related("assignment")

            # Get projects this student is working on (instead of groups)
            from .models import Project

            student_assignment_projects = Project.objects.filter(
                Q(student=student) | Q(collaborators=student),
                project_assignment__in=active_assignments,
            ).select_related("project_assignment")

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

            # Process choice-based assignments (team-based approach)
            for assignment in active_assignments.filter(assignment_type="choice_based"):
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
                            urgent_deadlines.append(("selection", days_left))

                    if assignment.deadline:
                        days_left = (assignment.deadline - now).days
                        if assignment.deadline < now:
                            overdue_count += 1
                            continue
                        elif days_left <= 7:
                            urgent_deadlines.append(("final", days_left))

                    if urgent_deadlines:
                        urgent_count += 1

            context.update(
                {
                    "urgent_assignments_count": urgent_count,
                    "overdue_assignments_count": overdue_count,
                    "pending_assignments_count": pending_count,
                }
            )

        # Cache briefly (5 min) so badges stay responsive; mutation views
        # also invalidate this via utils.clear_student_context_cache().
        cache.set(cache_key, context, 300)

    except StudentProfile.DoesNotExist:
        # Return default context if student profile doesn't exist
        pass
    except Exception:
        # Log the error but don't break the page
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Error in student_context processor")

    return context
