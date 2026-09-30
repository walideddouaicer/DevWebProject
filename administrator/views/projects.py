from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Project
from teacher.models import Module, ModuleAssignment, TeacherProfile

from ..models import AdminProfile
from ._auth import admin_required


@admin_required
def projects_list(request):
    """List all projects with filtering capabilities - FIXED VERSION"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    # Start with all projects
    projects = Project.objects.select_related("student__user", "module").prefetch_related(
        "collaborators__user"
    )

    # Apply filters (existing filter logic...)
    search_query = request.GET.get("search", "")
    if search_query:
        projects = projects.filter(
            Q(title__icontains=search_query)
            | Q(student__user__first_name__icontains=search_query)
            | Q(student__user__last_name__icontains=search_query)
            | Q(student__user__username__icontains=search_query)
        )

    # Filter by module
    module_id = request.GET.get("module")
    if module_id:
        projects = projects.filter(module_id=module_id)

    # Filter by teacher (through module assignments)
    teacher_id = request.GET.get("teacher")
    if teacher_id:
        teacher_modules = ModuleAssignment.objects.filter(
            teacher_id=teacher_id, is_active=True
        ).values_list("module_id", flat=True)
        projects = projects.filter(module_id__in=teacher_modules)

    # Filter by status
    status = request.GET.get("status")
    if status:
        projects = projects.filter(status=status)

    # Filter by project type
    project_type = request.GET.get("project_type")
    if project_type:
        projects = projects.filter(project_type=project_type)

    # Filter by academic year
    academic_year = request.GET.get("academic_year")
    if academic_year:
        projects = projects.filter(module__academic_year=academic_year)

    # Filter by date range
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        projects = projects.filter(created_at__gte=date_from)
    if date_to:
        projects = projects.filter(created_at__lte=date_to)

    # Order by latest first
    projects = projects.order_by("-updated_at")

    # Calculate statistics manually
    total_projects = projects.count()
    submitted_count = projects.filter(status="submitted").count()
    validated_count = projects.filter(status="validated").count()
    rejected_count = projects.filter(status="rejected").count()
    in_progress_count = projects.filter(status="in_progress").count()

    # Pagination
    paginator = Paginator(projects, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get filter options
    modules = Module.objects.filter(is_active=True).order_by("code")
    teachers = TeacherProfile.objects.select_related("user").order_by("user__first_name")
    academic_years = (
        Module.objects.values_list("academic_year", flat=True).distinct().order_by("academic_year")
    )

    context = {
        "admin": admin,
        "page_obj": page_obj,
        "modules": modules,
        "teachers": teachers,
        "academic_years": academic_years,
        "search_query": search_query,
        "project_types": Project.PROJECT_TYPES,
        "status_choices": Project.STATUS_CHOICES,
        # Add manually calculated counts
        "total_projects": total_projects,
        "submitted_count": submitted_count,
        "validated_count": validated_count,
        "rejected_count": rejected_count,
        "in_progress_count": in_progress_count,
        "selected_module": module_id,
        "selected_teacher": teacher_id,
        "selected_status": status,
        "selected_project_type": project_type,
        "selected_academic_year": academic_year,
        "date_from": date_from,
        "date_to": date_to,
    }

    return render(request, "administrator/projects_list.html", context)


@admin_required
def project_detail(request, project_id):
    """View detailed information about a specific project (read-only)"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    project = get_object_or_404(
        Project.objects.select_related("student__user", "module"), id=project_id
    )

    # Get project details
    deliverables = project.deliverables.all().order_by("-upload_date")
    milestones = project.milestones.all().order_by("due_date")
    comments = project.comments.all().select_related("author").order_by("-created_at")
    activities = project.activities.all().select_related("user").order_by("-created_at")
    collaborators = project.collaborators.all().select_related("user")

    # Get assigned teachers for this project's module
    assigned_teachers = []
    if project.module:
        assignments = ModuleAssignment.objects.filter(
            module=project.module, is_active=True
        ).select_related("teacher__user")
        assigned_teachers = [assignment.teacher for assignment in assignments]

    context = {
        "admin": admin,
        "project": project,
        "deliverables": deliverables,
        "milestones": milestones,
        "comments": comments,
        "activities": activities,
        "collaborators": collaborators,
        "assigned_teachers": assigned_teachers,
    }

    return render(request, "administrator/project_detail.html", context)


@admin_required
def reports_moderation(request):
    """Moderation queue for reported public projects (ROADMAP #2)"""
    from student.models import ProjectReport

    admin = get_object_or_404(AdminProfile, user=request.user)

    show = request.GET.get("show", "pending")  # 'pending', 'hidden', 'all'

    projects = (
        Project.objects.filter(reports__isnull=False)
        .distinct()
        .select_related("student__user", "module")
        .prefetch_related("reports__reporter")
    )

    if show == "pending":
        projects = projects.filter(reports__is_reviewed=False).distinct()
    elif show == "hidden":
        projects = projects.filter(is_hidden_by_admin=True)

    projects = projects.order_by("-report_count", "-updated_at")

    # Statistics
    total_reports = ProjectReport.objects.count()
    pending_reports = ProjectReport.objects.filter(is_reviewed=False).count()
    hidden_projects = Project.objects.filter(is_hidden_by_admin=True).count()

    context = {
        "admin": admin,
        "projects": projects,
        "show": show,
        "total_reports": total_reports,
        "pending_reports": pending_reports,
        "hidden_projects": hidden_projects,
    }

    return render(request, "administrator/reports_moderation.html", context)


@admin_required
def moderate_project(request, project_id):
    """Apply a moderation action to a reported project"""
    from student.models import Notification

    if request.method != "POST":
        return redirect("administrator:reports_moderation")

    project = get_object_or_404(Project, id=project_id)
    action = request.POST.get("action")
    notes = request.POST.get("admin_notes", "").strip()

    if action == "hide":
        project.is_hidden_by_admin = True
        project.is_public = False
        project.save(update_fields=["is_hidden_by_admin", "is_public"])
        project.reports.filter(is_reviewed=False).update(is_reviewed=True, admin_notes=notes)

        Notification.objects.create(
            recipient=project.student,
            project=project,
            notification_type="project_update",
            message=(
                f"Votre projet '{project.title}' a été retiré de la vitrine publique "
                f"suite à des signalements.{' Motif: ' + notes if notes else ''}"
            ),
        )
        messages.success(request, f"Projet '{project.title}' masqué de la vitrine publique.")

    elif action == "unhide":
        project.is_hidden_by_admin = False
        project.is_reported = False
        project.save(update_fields=["is_hidden_by_admin", "is_reported"])

        Notification.objects.create(
            recipient=project.student,
            project=project,
            notification_type="project_update",
            message=f"Votre projet '{project.title}' est de nouveau autorisé sur la vitrine publique.",
        )
        messages.success(request, f"Projet '{project.title}' réautorisé.")

    elif action == "dismiss":
        project.reports.filter(is_reviewed=False).update(is_reviewed=True, admin_notes=notes)
        project.is_reported = False
        project.save(update_fields=["is_reported"])
        messages.success(request, f"Signalements du projet '{project.title}' classés sans suite.")

    else:
        messages.error(request, "Action de modération invalide.")

    return redirect("administrator:reports_moderation")
