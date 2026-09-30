from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import manageable_assignments, teacher_required
from student.models import Project

from ..models import ModuleAssignment


@teacher_required
def dashboard(request):
    """Review queue first, then upcoming deadlines, then modules."""
    teacher = request.teacher
    assigned_modules = list(
        ModuleAssignment.objects.filter(teacher=teacher, is_active=True)
        .select_related("module")
        .annotate(
            enrolled_count=Count(
                "module__enrollments", filter=Q(module__enrollments__is_active=True), distinct=True
            ),
            project_count=Count("module__projects", distinct=True),
            waiting_count=Count(
                "module__projects",
                filter=Q(module__projects__status="submitted"),
                distinct=True,
            ),
        )
        .order_by("module__code")
    )
    module_ids = [a.module_id for a in assigned_modules]
    projects = Project.objects.filter(module_id__in=module_ids)

    review_queue = (
        projects.filter(status="submitted")
        .select_related("student__user", "module", "project_assignment")
        .prefetch_related("collaborators__user")
        .order_by("assignment_submitted_at", "updated_at")[:10]
    )
    now = timezone.now()
    upcoming = list(
        manageable_assignments(teacher)
        .filter(status="published", deadline__gte=now, deadline__lte=now + timedelta(days=21))
        .select_related("module")
        .order_by("deadline")[:6]
    )

    context = {
        "teacher": teacher,
        "assigned_modules": assigned_modules,
        "review_queue": review_queue,
        "waiting_total": projects.filter(status="submitted").count(),
        "upcoming": upcoming,
        "total_students": sum(a.enrolled_count for a in assigned_modules),
        "total_projects": projects.count(),
        "validated_projects": projects.filter(status="validated").count(),
        "drafts": manageable_assignments(teacher).filter(status="draft").count(),
    }
    return render(request, "teacher/dashboard.html", context)
