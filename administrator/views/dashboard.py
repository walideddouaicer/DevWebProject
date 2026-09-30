from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from accounts.models import PendingRegistration
from student.models import Project, StudentProfile
from teacher.models import Module, ModuleEnrollment, TeacherProfile

from ..models import AdminProfile
from ._auth import admin_required


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
    projects_in_progress = Project.objects.filter(status="in_progress").count()
    projects_submitted = Project.objects.filter(status="submitted").count()
    projects_validated = Project.objects.filter(status="validated").count()
    projects_rejected = Project.objects.filter(status="rejected").count()

    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_projects = Project.objects.filter(created_at__gte=thirty_days_ago).count()
    recent_enrollments = ModuleEnrollment.objects.filter(enrolled_at__gte=thirty_days_ago).count()

    # Top 5 active modules by enrollment, counted in one query (distinct avoids
    # the join multiplication that made the original code count in Python).
    modules_with_stats = list(
        Module.objects.filter(is_active=True)
        .annotate(
            student_count=Count(
                "enrollments", filter=Q(enrollments__is_active=True), distinct=True
            ),
            teacher_count=Count(
                "assignments", filter=Q(assignments__is_active=True), distinct=True
            ),
            project_count=Count("projects", distinct=True),
        )
        .order_by("-student_count", "code")[:5]
    )

    # Recent projects for activity feed
    latest_projects = Project.objects.select_related("student__user", "module").order_by(
        "-updated_at"
    )[:10]

    # Pending registrations count
    pending_registrations_count = PendingRegistration.objects.filter(is_approved=False).count()

    context = {
        "admin": admin,
        "total_projects": total_projects,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_modules": total_modules,
        "projects_in_progress": projects_in_progress,
        "projects_submitted": projects_submitted,
        "projects_validated": projects_validated,
        "projects_rejected": projects_rejected,
        "recent_projects": recent_projects,
        "recent_enrollments": recent_enrollments,
        "modules_with_stats": modules_with_stats,
        "latest_projects": latest_projects,
        "pending_registrations_count": pending_registrations_count,
    }

    return render(request, "administrator/dashboard.html", context)


@admin_required
def statistics(request):
    """Detailed statistics page"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    # Project statistics by type
    project_type_stats = []
    for type_key, type_name in Project.PROJECT_TYPES:
        count = Project.objects.filter(project_type=type_key).count()
        project_type_stats.append({"type": type_name, "count": count})

    # Project statistics by status
    status_stats = []
    for status_key, status_name in Project.STATUS_CHOICES:
        count = Project.objects.filter(status=status_key).count()
        status_stats.append({"status": status_name, "count": count})

    # Module statistics
    module_stats = (
        Module.objects.filter(is_active=True)
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True)),
            project_count=Count("projects"),
        )
        .order_by("-student_count")
    )

    # Teacher workload
    teacher_workload = TeacherProfile.objects.annotate(
        module_count=Count("module_assignments", filter=Q(module_assignments__is_active=True)),
        student_count=Count(
            "module_assignments__module__enrollments",
            filter=Q(
                module_assignments__is_active=True,
                module_assignments__module__enrollments__is_active=True,
            ),
        ),
    ).order_by("-module_count")

    context = {
        "admin": admin,
        "project_type_stats": project_type_stats,
        "status_stats": status_stats,
        "module_stats": module_stats,
        "teacher_workload": teacher_workload,
    }

    return render(request, "administrator/statistics.html", context)
