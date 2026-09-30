import logging
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import PendingRegistration
from ensa_project_manager.pagination import paginate
from student.models import Project, StudentProfile
from teacher.models import TeacherProfile

from ..models import AdminProfile
from ._auth import admin_required

logger = logging.getLogger(__name__)


@admin_required
def pending_registrations(request):
    """View pending user registrations"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    pending = PendingRegistration.objects.filter(is_approved=False).order_by("-created_at")

    # Get statistics
    total_pending = pending.count()
    student_pending = pending.filter(role="student").count()
    teacher_pending = pending.filter(role="teacher").count()

    page_obj = paginate(request, pending)
    context = {
        "admin": admin,
        "pending_registrations": page_obj,
        "page_obj": page_obj,
        "total_pending": total_pending,
        "student_pending": student_pending,
        "teacher_pending": teacher_pending,
    }

    return render(request, "administrator/pending_registrations.html", context)


@admin_required
def approve_registration(request, registration_id):
    """Approve a pending registration"""
    get_object_or_404(AdminProfile, user=request.user)

    registration = get_object_or_404(PendingRegistration, id=registration_id, is_approved=False)

    if request.method == "POST":
        from django.db import transaction

        from accounts.utils import send_approval_email

        try:
            # All-or-nothing: if profile creation fails (e.g. duplicate
            # student_id), no orphan User account is left behind.
            with transaction.atomic():
                user = User.objects.create(
                    username=registration.username,
                    email=registration.email,
                    first_name=registration.first_name,
                    last_name=registration.last_name,
                    is_active=True,
                )
                # Set the already hashed password directly
                user.password = registration.password
                user.save()

                # Create appropriate profile
                if registration.role == "student":
                    StudentProfile.objects.create(
                        user=user,
                        student_id=registration.student_id,
                        year_of_study=registration.year_of_study,
                        department=registration.department,
                    )
                    profile_type = "étudiant"
                elif registration.role == "teacher":
                    TeacherProfile.objects.create(
                        user=user,
                        teacher_id=registration.teacher_id or None,
                        department=registration.department,
                    )
                    profile_type = "enseignant"
                else:
                    profile_type = registration.get_role_display().lower()

                # Mark as approved
                registration.is_approved = True
                registration.approved_by = request.user
                registration.approved_at = timezone.now()
                registration.save()

            messages.success(
                request,
                f"Compte {profile_type} approuvé pour {registration.first_name} {registration.last_name}",
            )

            # Notify the user by email (console backend in dev)
            send_approval_email(registration)

        except Exception:
            logger.exception("Erreur lors de l'approbation")
            messages.error(
                request,
                "Erreur lors de l'approbation. Réessayez ; si le problème persiste, contactez l'administration.",
            )

    return redirect("administrator:pending_registrations")


@admin_required
def reject_registration(request, registration_id):
    """Reject a pending registration"""
    get_object_or_404(AdminProfile, user=request.user)

    registration = get_object_or_404(PendingRegistration, id=registration_id, is_approved=False)

    if request.method == "POST":
        try:
            name = f"{registration.first_name} {registration.last_name}"

            # TODO: Send rejection email before deleting
            registration.delete()

            messages.info(request, f"Demande d'inscription de {name} rejetée")
        except Exception:
            logger.exception("Erreur lors du rejet")
            messages.error(
                request,
                "Erreur lors du rejet. Réessayez ; si le problème persiste, contactez l'administration.",
            )

    return redirect("administrator:pending_registrations")


@admin_required
def users_list(request):
    """Unified users list with toggle between students and teachers"""
    admin = get_object_or_404(AdminProfile, user=request.user)

    # Get user type toggle (default to students)
    user_type = request.GET.get("type", "students")  # 'students' or 'teachers'

    # Apply basic filters
    search_query = request.GET.get("search", "")
    department_filter = request.GET.get("department", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    year_filter = request.GET.get("year_of_study", "")  # Define this for both user types

    if user_type == "teachers":
        # Get teachers data
        users = TeacherProfile.objects.select_related("user").order_by("user__first_name")

        # Apply search filter for teachers
        if search_query:
            users = users.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(teacher_id__icontains=search_query)
            )

        # Filter by department
        if department_filter:
            users = users.filter(department__icontains=department_filter)

        # Per-teacher stats in one query (students counted once per module taught)
        users = users.annotate(
            modules_count=Count(
                "module_assignments",
                filter=Q(module_assignments__is_active=True),
                distinct=True,
            ),
            students_taught=Count(
                "module_assignments__module__enrollments",
                filter=Q(
                    module_assignments__is_active=True,
                    module_assignments__module__enrollments__is_active=True,
                ),
            ),
        )

        # Get all teacher departments for filter
        all_departments = (
            TeacherProfile.objects.values_list("department", flat=True)
            .distinct()
            .order_by("department")
        )

    else:  # students
        # Get students data
        users = StudentProfile.objects.select_related("user").order_by("user__first_name")

        # Apply search filter for students
        if search_query:
            users = users.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(student_id__icontains=search_query)
            )

        # Filter by department
        if department_filter:
            users = users.filter(department__icontains=department_filter)

        # Filter by year of study (students only)
        if year_filter:
            users = users.filter(year_of_study=year_filter)

        # Per-student stats in one query (subqueries avoid join multiplication)
        owned = (
            Project.objects.filter(student=OuterRef("pk"))
            .values("student")
            .annotate(n=Count("pk"))
            .values("n")
        )
        collaborating = (
            Project.collaborators.through.objects.filter(studentprofile=OuterRef("pk"))
            .values("studentprofile")
            .annotate(n=Count("pk"))
            .values("n")
        )
        users = users.annotate(
            modules_count=Count(
                "module_enrollments", filter=Q(module_enrollments__is_active=True), distinct=True
            ),
            projects_count=Coalesce(Subquery(owned), 0) + Coalesce(Subquery(collaborating), 0),
        )

        # Get all student departments for filter
        all_departments = (
            StudentProfile.objects.values_list("department", flat=True)
            .distinct()
            .order_by("department")
        )

    # Apply date filters
    if date_from:
        users = [
            u
            for u in users
            if u.user.date_joined.date() >= datetime.strptime(date_from, "%Y-%m-%d").date()
        ]
    if date_to:
        users = [
            u
            for u in users
            if u.user.date_joined.date() <= datetime.strptime(date_to, "%Y-%m-%d").date()
        ]

    # Calculate statistics
    total_students = StudentProfile.objects.count()
    total_teachers = TeacherProfile.objects.count()

    # Recent registrations (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_students = StudentProfile.objects.filter(user__date_joined__gte=thirty_days_ago).count()
    recent_teachers = TeacherProfile.objects.filter(user__date_joined__gte=thirty_days_ago).count()

    # Department breakdown for current user type
    if user_type == "teachers":
        dept_breakdown = (
            TeacherProfile.objects.values("department")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
    else:
        dept_breakdown = (
            StudentProfile.objects.values("department")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )

    # Year breakdown (students only)
    year_breakdown = []
    if user_type == "students":
        year_breakdown = (
            StudentProfile.objects.values("year_of_study")
            .annotate(count=Count("id"))
            .order_by("year_of_study")
        )

    # Pagination
    paginator = Paginator(users, 25)  # Show 25 users per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get year choices for students filter
    year_choices = [(3, "3ème Année"), (4, "4ème Année"), (5, "5ème Année")]

    context = {
        "admin": admin,
        "page_obj": page_obj,
        "user_type": user_type,
        "search_query": search_query,
        "department_filter": department_filter,
        "date_from": date_from,
        "date_to": date_to,
        "selected_year": year_filter,
        "all_departments": all_departments,
        "year_choices": year_choices,
        # Statistics
        "total_students": total_students,
        "total_teachers": total_teachers,
        "recent_students": recent_students,
        "recent_teachers": recent_teachers,
        "current_type_count": len(users),
        "dept_breakdown": dept_breakdown,
        "year_breakdown": year_breakdown,
    }

    return render(request, "administrator/users_list.html", context)


@admin_required
def toggle_user_active(request, user_id):
    """Activate/deactivate a user account (students and teachers only)."""
    if request.method != "POST":
        return redirect("administrator:users_list")

    target = get_object_or_404(User, id=user_id)

    # Guards: never touch yourself or another administrator
    if target == request.user:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect("administrator:users_list")
    if AdminProfile.objects.filter(user=target).exists():
        messages.error(request, "Les comptes administrateur ne peuvent pas être désactivés ici.")
        return redirect("administrator:users_list")

    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])

    name = target.get_full_name() or target.username
    if target.is_active:
        messages.success(request, f"Le compte de {name} a été réactivé.")
    else:
        messages.success(
            request, f"Le compte de {name} a été désactivé. Il ne peut plus se connecter."
        )

    # Back to the right tab
    user_type = "teachers" if TeacherProfile.objects.filter(user=target).exists() else "students"
    return redirect(f"/administrator/users/list/?type={user_type}")
