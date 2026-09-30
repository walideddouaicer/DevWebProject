from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from student.models import Project, StudentProfile
from teacher.models import TeacherProfile

from ..models import AdminProfile
from ._auth import admin_required


@admin_required
def exports(request):
    """Export options page"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    context = {
        "admin": admin,
    }

    return render(request, "administrator/exports.html", context)


@admin_required
def export_projects(request):
    """Export all projects to Excel (honours the projects_list filters)"""
    from ..exports import build_projects_workbook, excel_response

    projects = (
        Project.objects.select_related("student__user", "module")
        .prefetch_related("collaborators__user")
        .order_by("-created_at")
    )

    # Reuse the same GET filters as the projects list
    status = request.GET.get("status")
    if status:
        projects = projects.filter(status=status)
    module_id = request.GET.get("module")
    if module_id:
        projects = projects.filter(module_id=module_id)
    project_type = request.GET.get("project_type")
    if project_type:
        projects = projects.filter(project_type=project_type)

    workbook = build_projects_workbook(projects)
    filename = f"projets_ensa_{timezone.now().strftime('%Y%m%d')}.xlsx"
    return excel_response(workbook, filename)


@admin_required
def export_statistics(request):
    """Export platform statistics as a PDF report"""
    from ..exports import build_statistics_pdf

    return build_statistics_pdf()


@admin_required
def export_users(request):
    """Export all users to Excel (one sheet per role)"""
    from ..exports import build_users_workbook, excel_response

    students = StudentProfile.objects.select_related("user").order_by("user__last_name")
    teachers = TeacherProfile.objects.select_related("user").order_by("user__last_name")

    workbook = build_users_workbook(students, teachers)
    filename = f"utilisateurs_ensa_{timezone.now().strftime('%Y%m%d')}.xlsx"
    return excel_response(workbook, filename)
