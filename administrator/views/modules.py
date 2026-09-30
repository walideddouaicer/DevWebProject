import logging

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ensa_project_manager.pagination import paginate
from student.models import Project
from teacher.models import Module, ModuleAssignment, ModuleEnrollment, TeacherProfile

from ..forms import AdminModuleForm
from ..models import AdminProfile
from ._auth import admin_required

logger = logging.getLogger(__name__)


@admin_required
def modules_list(request):
    """List all modules with management options - FIXED VERSION"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    # Get base queryset
    modules = Module.objects.all().order_by("-created_at")

    # Apply filters
    search_query = request.GET.get("search", "")
    if search_query:
        modules = modules.filter(Q(code__icontains=search_query) | Q(name__icontains=search_query))

    academic_year = request.GET.get("academic_year")
    if academic_year:
        modules = modules.filter(academic_year=academic_year)

    semester = request.GET.get("semester")
    if semester:
        modules = modules.filter(semester=semester)

    # Per-module counts in one query. distinct=True matters: three joined counts
    # would otherwise multiply each other (why the old code counted in Python loops).
    modules = modules.annotate(
        student_count=Count("enrollments", filter=Q(enrollments__is_active=True), distinct=True),
        teacher_count=Count("assignments", filter=Q(assignments__is_active=True), distinct=True),
        project_count=Count("projects", distinct=True),
    ).prefetch_related("assignments__teacher__user")
    modules_with_counts = list(modules)

    total_modules = len(modules_with_counts)
    active_modules = sum(1 for module in modules_with_counts if module.is_active)
    total_students_enrolled = sum(module.student_count for module in modules_with_counts)
    total_teachers_assigned = sum(module.teacher_count for module in modules_with_counts)

    # Get filter options
    academic_years = (
        Module.objects.values_list("academic_year", flat=True).distinct().order_by("academic_year")
    )

    page_obj = paginate(request, modules_with_counts)
    context = {
        "admin": admin,
        "modules": page_obj,
        "page_obj": page_obj,
        "academic_years": academic_years,
        "search_query": search_query,
        "selected_academic_year": academic_year,
        "selected_semester": semester,
        "semester_choices": Module._meta.get_field("semester").choices,
        # Add totals calculated manually
        "total_modules": total_modules,
        "active_modules": active_modules,
        "total_students_enrolled": total_students_enrolled,
        "total_teachers_assigned": total_teachers_assigned,
    }

    return render(request, "administrator/modules_list.html", context)


@admin_required
def module_create(request):
    """Create a new module (validated by AdminModuleForm)."""
    admin = get_object_or_404(AdminProfile, user=request.user)
    form = AdminModuleForm(request.POST or None, initial={"is_active": True})
    if request.method == "POST":
        if form.is_valid():
            module = form.save()
            messages.success(request, f"Module « {module.code} — {module.name} » créé avec succès.")
            return redirect("administrator:module_detail", module_id=module.id)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)

    context = {
        "admin": admin,
        "form": form,
        "semester_choices": Module._meta.get_field("semester").choices,
    }
    return render(request, "administrator/module_create.html", context)


@admin_required
def module_detail(request, module_id):
    """View detailed information about a module"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    module = get_object_or_404(Module, id=module_id)

    # Get module statistics
    enrollments = ModuleEnrollment.objects.filter(module=module, is_active=True).select_related(
        "student__user"
    )

    assignments = ModuleAssignment.objects.filter(module=module, is_active=True).select_related(
        "teacher__user"
    )

    module_projects = Project.objects.filter(module=module).select_related("student__user")

    context = {
        "admin": admin,
        "module": module,
        "enrollments": enrollments,
        "assignments": assignments,
        "module_projects": module_projects,
        "total_students": enrollments.count(),
        "total_teachers": assignments.count(),
        "total_projects": module_projects.count(),
    }

    return render(request, "administrator/module_detail.html", context)


@admin_required
def module_edit(request, module_id):
    """Edit module information (validated by AdminModuleForm; the code never changes)."""
    admin = get_object_or_404(AdminProfile, user=request.user)
    module = get_object_or_404(Module, id=module_id)

    if request.method == "POST":
        data = request.POST.copy()
        # Fields the page doesn't show keep their current value (checkboxes excepted).
        for field in ("classroom", "description"):
            if field not in data:
                data[field] = getattr(module, field)
        form = AdminModuleForm(data, instance=module)
        if form.is_valid():
            form.save()
            messages.success(request, f"Module « {module.code} » mis à jour avec succès.")
            return redirect("administrator:module_detail", module_id=module.id)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    else:
        form = AdminModuleForm(instance=module)

    context = {
        "admin": admin,
        "module": module,
        "form": form,
        "semester_choices": Module._meta.get_field("semester").choices,
    }
    return render(request, "administrator/module_edit.html", context)


@admin_required
def module_delete(request, module_id):
    """Delete a module (soft delete - set is_active to False)"""
    admin = get_object_or_404(AdminProfile, user=request.user)
    module = get_object_or_404(Module, id=module_id)

    if request.method == "POST":
        # Soft delete - set is_active to False
        module.is_active = False
        module.save()

        messages.success(request, f"Module '{module.code}' désactivé avec succès.")
        return redirect("administrator:modules_list")

    # Get statistics for confirmation
    student_count = ModuleEnrollment.objects.filter(module=module, is_active=True).count()
    teacher_count = ModuleAssignment.objects.filter(module=module, is_active=True).count()
    project_count = Project.objects.filter(module=module).count()

    context = {
        "admin": admin,
        "module": module,
        "student_count": student_count,
        "teacher_count": teacher_count,
        "project_count": project_count,
    }

    return render(request, "administrator/module_delete.html", context)


@admin_required
def assignments_management(request):
    """Manage teacher-module assignments - FIXED VERSION"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    # Get all active assignments
    assignments = (
        ModuleAssignment.objects.filter(is_active=True)
        .select_related("teacher__user", "module")
        .order_by("module__code")
    )

    # Get teachers and modules for new assignments
    teachers = TeacherProfile.objects.select_related("user").order_by("user__first_name")
    modules = Module.objects.filter(is_active=True).order_by("code")

    # Calculate unassigned modules manually
    assigned_module_ids = assignments.values_list("module_id", flat=True)
    unassigned_modules = modules.exclude(id__in=assigned_module_ids)

    # Calculate statistics manually for accuracy
    total_assignments = assignments.count()
    total_teachers = teachers.count()
    total_modules = modules.count()
    total_unassigned = unassigned_modules.count()

    # Workload per teacher in one query (distinct: two joined counts)
    teachers_with_workload = list(
        teachers.annotate(
            assignment_count=Count(
                "module_assignments", filter=Q(module_assignments__is_active=True), distinct=True
            ),
            student_count=Count(
                "module_assignments__module__enrollments",
                filter=Q(
                    module_assignments__is_active=True,
                    module_assignments__module__enrollments__is_active=True,
                ),
                distinct=True,
            ),
        )
    )

    context = {
        "admin": admin,
        "assignments": assignments,
        "teachers": teachers_with_workload,  # Now includes workload data
        "modules": modules,
        "unassigned_modules": unassigned_modules,
        # Add manual counts
        "total_assignments": total_assignments,
        "total_teachers": total_teachers,
        "total_modules": total_modules,
        "total_unassigned": total_unassigned,
    }

    return render(request, "administrator/assignments_management.html", context)


@admin_required
def assign_teacher_to_module(request):
    """Assign a teacher to a module"""
    get_object_or_404(AdminProfile, user=request.user)

    if request.method == "POST":
        teacher_id = request.POST.get("teacher_id")
        module_id = request.POST.get("module_id")

        if not teacher_id or not module_id:
            messages.error(request, "Veuillez sélectionner un enseignant et un module.")
            return redirect("administrator:assignments_management")

        try:
            teacher = TeacherProfile.objects.get(id=teacher_id)
            module = Module.objects.get(id=module_id)

            # Check if assignment already exists
            existing_assignment = ModuleAssignment.objects.filter(
                teacher=teacher, module=module
            ).first()

            if existing_assignment:
                if existing_assignment.is_active:
                    messages.info(
                        request,
                        f"{teacher.user.get_full_name()} est déjà assigné au module {module.code}.",
                    )
                else:
                    # Reactivate existing assignment
                    existing_assignment.is_active = True
                    existing_assignment.assigned_by = request.user
                    existing_assignment.save()
                    messages.success(
                        request,
                        f"{teacher.user.get_full_name()} a été réassigné au module {module.code}.",
                    )
            else:
                # Create new assignment
                ModuleAssignment.objects.create(
                    teacher=teacher, module=module, assigned_by=request.user, is_active=True
                )
                messages.success(
                    request,
                    f"{teacher.user.get_full_name()} a été assigné au module {module.code}.",
                )

        except (TeacherProfile.DoesNotExist, Module.DoesNotExist):
            messages.error(request, "Enseignant ou module introuvable.")
        except Exception:
            logger.exception("Erreur lors de l'assignation")
            messages.error(
                request,
                "Erreur lors de l'assignation. Réessayez ; si le problème persiste, contactez l'administration.",
            )

    return redirect("administrator:assignments_management")


@admin_required
@require_POST
def remove_assignment(request, assignment_id):
    """Remove a teacher-module assignment"""
    get_object_or_404(AdminProfile, user=request.user)

    try:
        assignment = ModuleAssignment.objects.get(id=assignment_id, is_active=True)
        assignment.is_active = False
        assignment.save()

        messages.success(
            request,
            f"Assignation de {assignment.teacher.user.get_full_name()} au module {assignment.module.code} supprimée.",
        )
    except ModuleAssignment.DoesNotExist:
        messages.error(request, "Assignation introuvable.")
    except Exception:
        logger.exception("Erreur lors de la suppression")
        messages.error(
            request,
            "Erreur lors de la suppression. Réessayez ; si le problème persiste, contactez l'administration.",
        )

    return redirect("administrator:assignments_management")


@admin_required
@require_POST
def remove_student_from_module(request, module_id, student_id):
    """Unenroll a student (soft: the enrollment is deactivated)."""
    module = get_object_or_404(Module, id=module_id)
    enrollment = (
        ModuleEnrollment.objects.filter(module=module, student_id=student_id, is_active=True)
        .select_related("student__user")
        .first()
    )
    if enrollment is None:
        message, ok = "Cet étudiant n'est pas inscrit à ce module.", False
    else:
        enrollment.is_active = False
        enrollment.save(update_fields=["is_active"])
        message, ok = (
            f"{enrollment.student.get_full_name()} a été désinscrit de {module.code}.",
            True,
        )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": ok, "message": message})
    (messages.success if ok else messages.error)(request, message)
    return redirect("administrator:module_detail", module_id=module.id)
