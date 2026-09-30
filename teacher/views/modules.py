import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.permissions import teacher_required
from ensa_project_manager.pagination import paginate
from student.models import Notification, Project

from ..forms import (
    AnnouncementForm,
    ModuleCreationForm,
)
from ..models import (
    ModuleAssignment,
    ModuleEnrollment,
    ProjectAssignment,
)

logger = logging.getLogger(__name__)


@teacher_required
def modules_list(request):
    """Modules the teacher teaches, with enrolment and project counts."""
    assigned_modules = (
        ModuleAssignment.objects.filter(teacher=request.teacher, is_active=True)
        .select_related("module")
        .annotate(
            enrolled_count=Count(
                "module__enrollments", filter=Q(module__enrollments__is_active=True), distinct=True
            ),
            project_count=Count("module__projects", distinct=True),
            waiting_count=Count(
                "module__projects", filter=Q(module__projects__status="submitted"), distinct=True
            ),
        )
        .order_by("module__code")
    )
    return render(
        request,
        "teacher/modules_list.html",
        {"teacher": request.teacher, "assigned_modules": assigned_modules},
    )


@teacher_required
def module_detail(request, module_id):
    """Detailed view of a specific module"""
    teacher = request.teacher

    # Verify teacher has access to this module
    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
        )
        module = assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect("teacher:modules_list")

    # Get module statistics
    enrollments = ModuleEnrollment.objects.filter(module=module, is_active=True).select_related(
        "student__user"
    )

    # Import here to avoid circular imports

    # Get projects from this module
    module_projects = (
        Project.objects.filter(module=module)
        .select_related("student__user")
        .order_by("-updated_at")
    )

    # Statistics
    total_students = enrollments.count()
    total_projects = module_projects.count()
    submitted_projects = module_projects.filter(status="submitted").count()
    validated_projects = module_projects.filter(status="validated").count()

    # Recent announcements for this module
    announcements = module.announcements.select_related("teacher__user")[:5]

    module_assignments = ProjectAssignment.objects.filter(module=module).order_by("-created_at")

    context = {
        "teacher": teacher,
        "module": module,
        "assignment": assignment,
        "enrollments": enrollments,
        "module_projects": module_projects[:10],  # Show recent 10
        "total_students": total_students,
        "total_projects": total_projects,
        "submitted_projects": submitted_projects,
        "validated_projects": validated_projects,
        "module_assignments": module_assignments,
        "announcements": announcements,
    }

    return render(request, "teacher/module_detail.html", context)


@teacher_required
def module_projects(request, module_id):
    """View all projects for a specific module"""
    teacher = request.teacher

    # Verify teacher has access to this module
    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
        )
        module = assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect("teacher:modules_list")

    # Import here to avoid circular imports

    # Get all projects from this module
    projects = (
        Project.objects.filter(module=module)
        .select_related("student__user", "module")
        .annotate(
            collaborator_count=Count("collaborators", distinct=True),
            deliverable_count=Count("deliverables", distinct=True),
        )
        .order_by("-updated_at")
    )

    # Filter by status if requested
    status_filter = request.GET.get("status", "")
    if status_filter:
        projects = projects.filter(status=status_filter)

    # Statistics
    total_projects = projects.count()
    submitted_projects = projects.filter(status="submitted").count()
    validated_projects = projects.filter(status="validated").count()
    rejected_projects = projects.filter(status="rejected").count()

    page_obj = paginate(request, projects)
    context = {
        "teacher": teacher,
        "module": module,
        "projects": page_obj,
        "page_obj": page_obj,
        "total_projects": total_projects,
        "submitted_projects": submitted_projects,
        "validated_projects": validated_projects,
        "rejected_projects": rejected_projects,
        "status_filter": status_filter,
    }

    return render(request, "teacher/module_projects.html", context)


@teacher_required
def module_management(request, module_id):
    """Former roster page, merged into the module page."""
    return redirect("teacher:module_detail", module_id=module_id)


@teacher_required
@require_http_methods(["POST"])
def post_module_announcement(request, module_id):
    """Broadcast an announcement to every active student of a module."""

    from ensa_project_manager.emails import absolute_url, send_templated_email, wants_email

    from ..models import ModuleAnnouncement

    teacher = request.teacher

    try:
        module_assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
        )
        module = module_assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect("teacher:modules_list")

    form = AnnouncementForm(request.POST)
    if not form.is_valid():
        messages.error(
            request,
            "Le titre (200 caractères max.) et le contenu (5000 max.) de l'annonce sont obligatoires.",
        )
        return redirect("teacher:module_detail", module_id=module.id)
    title, content = form.cleaned_data["title"], form.cleaned_data["content"]

    ModuleAnnouncement.objects.create(module=module, teacher=teacher, title=title, content=content)

    teacher_name = teacher.user.get_full_name() or teacher.user.username
    enrollments = list(
        ModuleEnrollment.objects.filter(module=module, is_active=True).select_related(
            "student__user__preferences"
        )
    )

    # In-app notifications (bulk)
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=enrollment.student,
                notification_type="announcement",
                message=f"[{module.code}] {title} — {content[:180]}{'...' if len(content) > 180 else ''}",
            )
            for enrollment in enrollments
        ]
    )

    # Emails, respecting each student's preferences
    emailed = 0
    for enrollment in enrollments:
        user = enrollment.student.user
        if not wants_email(user, "project_notifications"):
            continue
        if send_templated_email(
            f"[{module.code}] {title}",
            "announcement",
            {
                "user": user,
                "teacher_name": teacher_name,
                "module": module,
                "title": title,
                "content": content,
                "modules_url": absolute_url("student:my_modules"),
            },
            [user.email],
        ):
            emailed += 1

    messages.success(
        request,
        f"Annonce publiée: {len(enrollments)} étudiant(s) notifié(s)"
        + (f", {emailed} email(s) envoyé(s)." if emailed else "."),
    )
    return redirect("teacher:module_detail", module_id=module.id)


@teacher_required
def export_module_roster(request, module_id):
    """Download the module's enrolled-students list as Excel."""

    from administrator.exports import build_module_roster_workbook, excel_response

    teacher = request.teacher

    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
        )
        module = assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect("teacher:modules_list")

    enrollments = (
        ModuleEnrollment.objects.filter(module=module, is_active=True)
        .select_related("student__user")
        .order_by("student__user__last_name")
    )

    workbook = build_module_roster_workbook(module, enrollments)
    filename = f"etudiants_{module.code}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    return excel_response(workbook, filename)


@teacher_required
@require_http_methods(["GET"])
def get_module_students(request, module_id):
    """API endpoint to get students for a module"""
    try:
        # Verify teacher has access to this module
        module_assignment = ModuleAssignment.objects.get(
            teacher=request.teacher, module_id=module_id, is_active=True
        )
        module = module_assignment.module

        # Get enrolled students
        enrollments = ModuleEnrollment.objects.filter(module=module, is_active=True).select_related(
            "student__user"
        )

        students_data = []
        for enrollment in enrollments:
            student = enrollment.student
            students_data.append(
                {
                    "id": student.id,
                    "username": student.user.username,
                    "full_name": student.user.get_full_name(),
                    "student_id": student.student_id,
                    "year_display": student.get_year_of_study_display(),
                    "initials": (
                        (student.user.first_name[:1] + student.user.last_name[:1])
                        if student.user.first_name and student.user.last_name
                        else student.user.username[:2]
                    ).upper(),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "students": students_data,
                "module": {"id": module.id, "code": module.code, "name": module.name},
            }
        )

    except ModuleAssignment.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Module non trouvé ou accès non autorisé"}, status=403
        )
    except Exception:
        logger.exception("get_module_students failed")
        return JsonResponse({"success": False, "error": "Erreur interne."}, status=500)


def check_teacher_module_access(teacher, module):
    """Helper function to check if teacher has access to a module"""
    return ModuleAssignment.objects.filter(teacher=teacher, module=module, is_active=True).exists()


@teacher_required
@transaction.atomic
def create_teacher_module(request):
    """Allow teachers to create new modules directly (no approval needed)"""
    teacher = request.teacher

    if request.method == "POST":
        form = ModuleCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    module = form.save(commit=False)
                    module.primary_teacher = teacher
                    module.created_by_teacher = True
                    module.is_active = True  # Active immediately, no approval needed
                    module.save()

                    # Automatically assign the teacher to the module
                    ModuleAssignment.objects.create(
                        teacher=teacher,
                        module=module,
                        assigned_by=teacher.user,  # Self-assigned
                        is_active=True,
                    )

                    messages.success(
                        request,
                        f"Module {module.code} — {module.name} créé. "
                        "Il est actif : les étudiants peuvent s'y inscrire.",
                    )
                    return redirect("teacher:module_detail", module_id=module.id)

            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
            except Exception:
                logger.exception("Erreur lors de la création")
                messages.error(
                    request,
                    "Erreur lors de la création. Réessayez ; si le problème persiste, contactez l'administration.",
                )
    else:
        form = ModuleCreationForm()

    context = {
        "teacher": teacher,
        "form": form,
    }

    return render(request, "teacher/modules/create.html", context)


@teacher_required
def my_modules(request):
    """Former duplicate of the modules list."""
    return redirect("teacher:modules_list")
