"""Navigation badges for every role (PLAN P3.4).

One processor replaces the three per-app ones. Each badge is a single indexed COUNT,
so nothing is cached: badges are always exact (the old hour-bucketed caches went
stale whenever a notification was created outside the invalidation paths).
"""

from datetime import timedelta

from django.utils import timezone

from .permissions import get_profiles, get_role, teacher_module_ids


def badges(request):
    """Role, badge counts, navigation and theme for every template."""
    context = _badges(request)
    role = context.get("user_role")
    if request.user.is_authenticated:
        from ui.navigation import HOME, build_navigation

        # Accounts without a role profile (e.g. a bare Django superuser) get no app nav.
        context["navigation"] = build_navigation(role, request.path, context) if role else []
        context["home_url_name"] = HOME.get(role, "public:homepage")
        preferences = getattr(request.user, "preferences", None)
        context["theme"] = preferences.theme_preference if preferences else "auto"
        context["theme_from_server"] = True
    return context


def _badges(request):
    user = request.user
    if not user.is_authenticated:
        return {"user_role": None}
    role = get_role(user)
    profiles = get_profiles(user)
    context = {"user_role": role}

    if profiles["student"]:
        from student.models import CollaborationInvitation, Notification

        student = profiles["student"]
        context["invitation_count"] = CollaborationInvitation.objects.filter(
            recipient=student, status="pending"
        ).count()
        context["unread_notifications_count"] = Notification.objects.filter(
            recipient=student, is_read=False
        ).count()

    if profiles["teacher"]:
        from student.models import Project
        from teacher.models import ProjectAssignment

        module_ids = teacher_module_ids(profiles["teacher"])
        context["ungraded_projects_count"] = Project.objects.filter(
            module_id__in=module_ids, status="submitted"
        ).count()
        now = timezone.now()
        context["urgent_deadlines_count"] = ProjectAssignment.objects.filter(
            module_id__in=module_ids,
            status="published",
            deadline__gt=now,
            deadline__lte=now + timedelta(days=7),
        ).count()

    if profiles["admin"]:
        from accounts.models import PendingRegistration
        from student.models import Project

        context["pending_registrations_count"] = PendingRegistration.objects.filter(
            is_approved=False
        ).count()
        context["reported_projects_count"] = Project.objects.filter(
            is_reported=True, is_hidden_by_admin=False
        ).count()

    return context
