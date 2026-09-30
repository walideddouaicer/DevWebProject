import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import (
    StudentProfile,
)

logger = logging.getLogger(__name__)


@login_required
def join_module(request):
    """Allow students to join a module using a code"""
    student = get_object_or_404(StudentProfile, user=request.user)

    if request.method == "POST":
        module_code = request.POST.get("module_code", "").strip().upper()

        if not module_code:
            messages.error(request, "Veuillez entrer un code de module.")
            return redirect("student:dashboard")

        try:
            # Import here to avoid circular imports
            from teacher.models import Module, ModuleEnrollment

            module = Module.objects.get(code=module_code, is_active=True)

            # Check if already enrolled
            enrollment, created = ModuleEnrollment.objects.get_or_create(
                student=student, module=module, defaults={"is_active": True}
            )

            if created:
                enrollment.attach_published_assignments()
                messages.success(
                    request, f"Vous avez rejoint le module '{module.name}' avec succès!"
                )
            elif enrollment.is_active:
                messages.info(request, f"Vous êtes déjà inscrit au module '{module.name}'.")
            else:
                # Reactivate if was previously inactive
                enrollment.is_active = True
                enrollment.save()
                enrollment.attach_published_assignments()
                messages.success(request, f"Vous avez rejoint à nouveau le module '{module.name}'!")

        except Module.DoesNotExist:
            messages.error(
                request,
                f"Aucun module trouvé avec le code '{module_code}'. Vérifiez le code et réessayez.",
            )
        except Exception:
            logger.exception("join_module failed")
            messages.error(request, "Une erreur est survenue. Veuillez réessayer.")

    return redirect("student:dashboard")


@login_required
def my_modules(request):
    """Display student's enrolled modules"""
    student = get_object_or_404(StudentProfile, user=request.user)

    # Import here to avoid circular imports
    from teacher.models import ModuleEnrollment

    # Get active enrollments
    enrollments = (
        ModuleEnrollment.objects.filter(student=student, is_active=True)
        .select_related("module")
        .prefetch_related("module__assignments__teacher__user")
        .order_by("-enrolled_at")
    )

    context = {
        "student": student,
        "enrollments": enrollments,
    }

    return render(request, "student/my_modules.html", context)


@login_required
@require_POST
def leave_module(request, module_id):
    """Allow student to leave a module"""
    student = get_object_or_404(StudentProfile, user=request.user)

    # Import here to avoid circular imports
    from teacher.models import Module, ModuleEnrollment

    try:
        module = Module.objects.get(id=module_id)
        enrollment = ModuleEnrollment.objects.get(student=student, module=module, is_active=True)

        enrollment.is_active = False
        enrollment.save()

        messages.success(request, f"Vous avez quitté le module '{module.name}'.")

    except (Module.DoesNotExist, ModuleEnrollment.DoesNotExist):
        messages.error(request, "Module non trouvé ou vous n'êtes pas inscrit à ce module.")

    return redirect("student:my_modules")
