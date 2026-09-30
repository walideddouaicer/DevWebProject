"""Role checks and object-access helpers shared by every app (PLAN P1.1).

Roles come from which profile row a User has; administrator wins over teacher, which
wins over student (same order as `smart_redirect`).

    @student_required
    def view(request, ...):
        request.student      # the StudentProfile

Anonymous users are redirected to the login page (with ?next=); authenticated users
with the wrong role get a 403.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

ROLE_ATTRIBUTES = {
    "admin": "admin_profile",
    "teacher": "teacher",
    "student": "student",
}


def get_profiles(user):
    """Return {'admin': AdminProfile|None, 'teacher': ..., 'student': ...}, cached on the user."""
    if not user.is_authenticated:
        return {"admin": None, "teacher": None, "student": None}
    cached = getattr(user, "_role_profiles", None)
    if cached is None:
        from administrator.models import AdminProfile
        from student.models import StudentProfile
        from teacher.models import TeacherProfile

        cached = {
            "admin": AdminProfile.objects.filter(user=user).first(),
            "teacher": TeacherProfile.objects.filter(user=user).first(),
            "student": StudentProfile.objects.filter(user=user).first(),
        }
        user._role_profiles = cached
    return cached


def get_role(user):
    """'admin', 'teacher', 'student' or None."""
    profiles = get_profiles(user)
    for role in ("admin", "teacher", "student"):
        if profiles[role] is not None:
            return role
    return None


def role_required(role):
    attribute = ROLE_ATTRIBUTES[role]

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            profile = get_profiles(request.user)[role]
            if profile is None:
                raise PermissionDenied(f"Réservé au rôle « {role} ».")
            setattr(request, attribute, profile)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


student_required = role_required("student")
teacher_required = role_required("teacher")
admin_required = role_required("admin")


# ---------------------------------------------------------------- object access


def member_projects(student, queryset=None):
    """Projects the student owns or collaborates on (deduplicated)."""
    from student.models import Project

    queryset = Project.objects.all() if queryset is None else queryset
    return queryset.filter(Q(student=student) | Q(collaborators=student)).distinct()


def get_project_for_member(student, project_id, queryset=None):
    """The project if the student is its owner or a collaborator, else 404."""
    return get_object_or_404(member_projects(student, queryset), pk=project_id)


def get_project_for_owner(student, project_id, queryset=None):
    """The project if the student owns it, else 404."""
    from student.models import Project

    queryset = Project.objects.all() if queryset is None else queryset
    return get_object_or_404(queryset, pk=project_id, student=student)


def teacher_module_ids(teacher):
    """IDs of the modules the teacher actively teaches."""
    from teacher.models import ModuleAssignment

    return list(
        ModuleAssignment.objects.filter(teacher=teacher, is_active=True).values_list(
            "module_id", flat=True
        )
    )


def get_project_for_teacher(teacher, project_id, queryset=None):
    """The project if it belongs to one of the teacher's modules, else 404."""
    from student.models import Project

    queryset = Project.objects.all() if queryset is None else queryset
    return get_object_or_404(queryset, pk=project_id, module_id__in=teacher_module_ids(teacher))


def manageable_assignments(teacher):
    """Assignments of every module the teacher actively teaches (co-teachers included)."""
    from teacher.models import ProjectAssignment

    return ProjectAssignment.objects.filter(module_id__in=teacher_module_ids(teacher))
