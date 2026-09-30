import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from student.models import Notification, Project

from ..forms import (
    ModuleCreationForm,
)
from ..models import (
    ModuleAssignment,
    ModuleEnrollment,
    ProjectAssignment,
    TeacherProfile,
)
from .assignments import get_teacher_or_error

logger = logging.getLogger(__name__)


@login_required
def modules_list(request):
    """View to display all modules assigned to the teacher"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant. Contactez l'administrateur.")
        return redirect("login")

    # Get all assigned modules with related data
    assigned_modules = (
        ModuleAssignment.objects.filter(teacher=teacher, is_active=True)
        .select_related("module")
        .prefetch_related("module__enrollments__student__user")
    )

    context = {
        "teacher": teacher,
        "assigned_modules": assigned_modules,
    }

    return render(request, "teacher/modules_list.html", context)


@login_required
def module_detail(request, module_id):
    """Detailed view of a specific module"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

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
    from student.models import Project

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
        "announcements": announcements,
    }

    return render(request, "teacher/module_detail.html", context)


@login_required
def module_projects(request, module_id):
    """View all projects for a specific module"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

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
    from student.models import Project

    # Get all projects from this module
    projects = (
        Project.objects.filter(module=module)
        .select_related("student__user")
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

    context = {
        "teacher": teacher,
        "module": module,
        "projects": projects,
        "total_projects": total_projects,
        "submitted_projects": submitted_projects,
        "validated_projects": validated_projects,
        "rejected_projects": rejected_projects,
        "status_filter": status_filter,
    }

    return render(request, "teacher/module_projects.html", context)


@login_required
def module_management(request, module_id):
    """Module management interface for teachers"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    try:
        assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
        )
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect("teacher:modules_list")
    module = assignment.module

    enrollments = ModuleEnrollment.objects.filter(module=module, is_active=True).select_related(
        "student__user"
    )
    context = {
        "teacher": teacher,
        "module": module,
        "assignment": assignment,
        "enrollments": enrollments,
    }
    return render(request, "teacher/module_management.html", context)


@login_required
@require_http_methods(["POST"])
def post_module_announcement(request, module_id):
    """Broadcast an announcement to every active student of a module."""

    from ensa_project_manager.emails import absolute_url, send_templated_email
    from student.models import UserPreferences

    from ..models import ModuleAnnouncement

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    try:
        module_assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
        )
        module = module_assignment.module
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Vous n'avez pas accès à ce module.")
        return redirect("teacher:modules_list")

    title = request.POST.get("title", "").strip()
    content = request.POST.get("content", "").strip()

    if not title or not content:
        messages.error(request, "Le titre et le contenu de l'annonce sont obligatoires.")
        return redirect("teacher:module_detail", module_id=module.id)

    ModuleAnnouncement.objects.create(module=module, teacher=teacher, title=title, content=content)

    teacher_name = teacher.user.get_full_name() or teacher.user.username
    enrollments = ModuleEnrollment.objects.filter(module=module, is_active=True).select_related(
        "student__user"
    )

    # In-app notifications (bulk)
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=enrollment.student,
                notification_type="announcement",
                message=f"📢 [{module.code}] {title} — {content[:180]}{'...' if len(content) > 180 else ''}",
            )
            for enrollment in enrollments
        ]
    )

    # Emails, respecting each student's preferences
    emailed = 0
    for enrollment in enrollments:
        user = enrollment.student.user
        if not user.email:
            continue
        prefs = UserPreferences.objects.filter(user=user).first()
        if prefs and not (prefs.email_notifications and prefs.project_notifications):
            continue
        if prefs and prefs.email_digest:
            # Digest users get the announcement in their daily summary instead
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
        f"Annonce publiée: {enrollments.count()} étudiant(s) notifié(s)"
        + (f", {emailed} email(s) envoyé(s)." if emailed else "."),
    )
    return redirect("teacher:module_detail", module_id=module.id)


@login_required
def export_module_roster(request, module_id):
    """Download the module's enrolled-students list as Excel."""

    from administrator.exports import build_module_roster_workbook, excel_response

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

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


@login_required
@require_http_methods(["GET"])
def get_module_students(request, module_id):
    """API endpoint to get students for a module"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)

        # Verify teacher has access to this module
        module_assignment = ModuleAssignment.objects.get(
            teacher=teacher, module_id=module_id, is_active=True
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

    except (TeacherProfile.DoesNotExist, ModuleAssignment.DoesNotExist):
        return JsonResponse(
            {"success": False, "error": "Module non trouvé ou accès non autorisé"}, status=403
        )
    except Exception:
        logger.exception("get_module_students failed")
        return JsonResponse({"success": False, "error": "Erreur interne."}, status=500)


def check_teacher_module_access(teacher, module):
    """Helper function to check if teacher has access to a module"""
    return ModuleAssignment.objects.filter(teacher=teacher, module=module, is_active=True).exists()


@login_required
@transaction.atomic
def create_teacher_module(request):
    """Allow teachers to create new modules directly (no approval needed)"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

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

                    # ❌ REMOVED: ProjectActivity creation (was causing the error)
                    # No need to log module creation as project activity

                    messages.success(
                        request,
                        f"✅ Module '{module.code} - {module.name}' créé avec succès! "
                        f"Votre module est maintenant actif et les étudiants peuvent s'inscrire.",
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


@login_required
def my_modules(request):
    """Display teacher's modules - updated for direct creation"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    # Get teacher's assigned modules (both admin-assigned and self-created)
    module_assignments = (
        ModuleAssignment.objects.filter(teacher=teacher, is_active=True)
        .select_related("module")
        .order_by("-assigned_at")
    )

    modules_with_stats = []
    for assignment in module_assignments:
        module = assignment.module

        # Calculate statistics
        enrolled_count = ModuleEnrollment.objects.filter(module=module, is_active=True).count()

        project_assignments_count = ProjectAssignment.objects.filter(
            teacher=teacher, module=module
        ).count()

        total_projects_count = Project.objects.filter(module=module).count()

        # Get recent students for preview
        recent_students = (
            ModuleEnrollment.objects.filter(module=module, is_active=True)
            .select_related("student__user")
            .order_by("-enrolled_at")[:10]
        )

        modules_with_stats.append(
            {
                "assignment": assignment,
                "module": module,
                "enrolled_count": enrolled_count,
                "project_assignments_count": project_assignments_count,
                "total_projects_count": total_projects_count,
                "recent_students": recent_students,
                "is_self_created": module.created_by_teacher and module.primary_teacher == teacher,
                "creation_status": "active",  # Always active now
            }
        )

    context = {
        "teacher": teacher,
        "modules_with_stats": modules_with_stats,
        "pending_modules_count": 0,  # No more pending modules
    }

    return render(request, "teacher/modules/my_modules.html", context)
