from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from student.models import Project

from ..models import (
    ModuleAssignment,
    TeacherProfile,
)


@login_required
def dashboard(request):
    """Enhanced teacher dashboard with module and project data"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant. Contactez l'administrateur.")
        return redirect("login")

    # Get teacher's assigned modules
    assigned_modules = ModuleAssignment.objects.filter(
        teacher=teacher, is_active=True
    ).select_related("module")

    # Get teacher's module IDs
    teacher_module_ids = assigned_modules.values_list("module", flat=True)

    # Import here to avoid circular imports

    # Get projects from teacher's modules
    teacher_projects = Project.objects.filter(module__in=teacher_module_ids)

    # Calculate statistics
    total_modules = assigned_modules.count()
    total_students = 0
    total_projects = teacher_projects.count()
    pending_projects = teacher_projects.filter(status="submitted").count()
    validated_projects = teacher_projects.filter(status="validated").count()

    # Count total students across all modules
    for assignment in assigned_modules:
        total_students += assignment.module.get_enrolled_students_count()

    # Get recent modules for display
    recent_modules = assigned_modules[:5]  # Show 5 most recent

    # Get recent projects for the activity section
    recent_projects = teacher_projects.select_related("student__user", "module").order_by(
        "-updated_at"
    )[:5]

    context = {
        "teacher": teacher,
        "total_modules": total_modules,
        "total_students": total_students,
        "total_projects": total_projects,
        "pending_projects": pending_projects,
        "validated_projects": validated_projects,
        "recent_modules": recent_modules,
        "recent_projects": recent_projects,
        "assigned_modules": assigned_modules,
    }

    return render(request, "teacher/dashboard.html", context)
