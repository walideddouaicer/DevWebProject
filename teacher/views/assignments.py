import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.permissions import manageable_assignments, teacher_module_ids, teacher_required
from student.models import Notification, Project, StudentProfile

from ..forms import (
    BulkProjectActionForm,
    ProjectAssignmentForm,
    ProjectOptionForm,
    StudentSelectionForm,
)
from ..models import (
    DirectStudentAssignment,
    Module,
    ProjectOption,
    TeacherProfile,
)

logger = logging.getLogger(__name__)


@login_required
def export_assignment_results(request, assignment_id):
    """Download an assignment's teams, statuses and grades as Excel."""
    from django.utils import timezone

    from administrator.exports import build_assignment_results_workbook, excel_response

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    assignment = get_object_or_404(manageable_assignments(teacher), id=assignment_id)

    projects = (
        assignment.submitted_projects.select_related("student__user", "selected_option")
        .prefetch_related("collaborators__user")
        .order_by("student__user__last_name")
    )

    workbook = build_assignment_results_workbook(assignment, projects)
    safe_title = "".join(ch if ch.isalnum() else "_" for ch in assignment.title)[:40]
    filename = f"resultats_{safe_title}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    return excel_response(workbook, filename)


@login_required
@require_http_methods(["POST"])
def bulk_project_action(request, assignment_id):
    """Validate or request revision on several submitted projects at once."""
    from student.models import Project

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    assignment = get_object_or_404(manageable_assignments(teacher), id=assignment_id)

    form = BulkProjectActionForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("teacher:assignment_progress", assignment_id=assignment.id)
    action = form.cleaned_data["action"]
    project_ids = form.cleaned_data["project_ids"]
    content = form.cleaned_data["content"]

    # Only submitted projects of THIS assignment can be processed
    projects = Project.objects.filter(
        id__in=project_ids, project_assignment=assignment, status="submitted"
    )

    processed = 0
    for project in projects:
        if action == "validate":
            project.validate(by=teacher)
        else:
            project.request_revision(by=teacher, message=content)
        processed += 1

    skipped = len(project_ids) - processed
    if action == "validate":
        messages.success(request, f"{processed} projet(s) validé(s).")
    else:
        messages.success(request, f"Révision demandée pour {processed} projet(s).")
    if skipped:
        messages.warning(
            request, f"{skipped} projet(s) ignoré(s) (non soumis ou hors de ce devoir)."
        )

    return redirect("teacher:assignment_progress", assignment_id=assignment.id)


def get_teacher_or_error(request):
    """Helper function to get teacher profile with consistent error handling"""
    try:
        return TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return None


@teacher_required
def assignments_dashboard(request):
    """All assignments of the teacher's modules: drafts, open, closed."""
    teacher = request.teacher
    now = timezone.now()
    assignments = (
        manageable_assignments(teacher)
        .select_related("module", "teacher__user")
        .annotate(
            project_count=Count("submitted_projects", distinct=True),
            waiting_count=Count(
                "submitted_projects",
                filter=Q(submitted_projects__status="submitted"),
                distinct=True,
            ),
        )
        .order_by("deadline")
    )
    module_filter = request.GET.get("module", "")
    if module_filter.isdigit():
        assignments = assignments.filter(module_id=int(module_filter))
    assignments = list(assignments)
    groups = {
        "drafts": [a for a in assignments if a.status == "draft"],
        "open": [a for a in assignments if a.status == "published" and a.deadline >= now],
        "closed": [
            a
            for a in assignments
            if a.status in ("completed", "in_progress")
            or (a.status == "published" and a.deadline < now)
        ],
    }
    context = {
        "teacher": teacher,
        "groups": groups,
        "total": len(assignments),
        "modules": Module.objects.filter(id__in=teacher_module_ids(teacher)).order_by("code"),
        "module_filter": module_filter,
    }
    return render(request, "teacher/assignments/dashboard.html", context)


@teacher_required
def assignment_detail(request, assignment_id):
    """Overview of one assignment: status, hand-in progress, subjects, next step."""
    teacher = request.teacher
    assignment = get_object_or_404(
        manageable_assignments(teacher).select_related("module", "teacher__user"), id=assignment_id
    )
    projects = assignment.submitted_projects.all()
    counts = {row["status"]: row["n"] for row in projects.values("status").annotate(n=Count("id"))}
    options = assignment.project_options.annotate(
        projects_count=Count("submitted_projects", distinct=True)
    ).order_by("order", "title")
    context = {
        "teacher": teacher,
        "assignment": assignment,
        "options": options,
        "counts": counts,
        "project_total": sum(counts.values()),
        "expected_students": assignment.get_total_students(),
        "completion": assignment.get_completion_percentage(),
        "direct_count": assignment.direct_assignments.count(),
        "recent_projects": projects.select_related("student__user")
        .prefetch_related("collaborators__user")
        .order_by("-updated_at")[:8],
    }
    return render(request, "teacher/assignments/detail.html", context)


@login_required
def assignment_teams(request, assignment_id):
    """View all teams formed through project collaboration - NEW VIEW"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    assignment = get_object_or_404(manageable_assignments(teacher), id=assignment_id)

    # Get all projects for this assignment with their teams
    projects = (
        assignment.submitted_projects.select_related("student__user")
        .prefetch_related("collaborators__user")
        .order_by("-created_at")
    )

    # Build comprehensive team data
    teams_data = []
    total_students_in_teams = set()

    for project in projects:
        team_members = project.get_team_members()

        # Track all students in teams
        for member in team_members:
            total_students_in_teams.add(member.id)

        team_info = {
            "project": project,
            "team_leader": project.student,
            "collaborators": list(project.collaborators.all()),
            "all_members": team_members,
            "team_size": len(team_members),
            "is_valid_size": project.is_team_size_valid(),
            "size_status": project.get_team_size_status(),
            "selected_option": project.selected_option,
            "status": project.status,
            "submitted_at": project.assignment_submitted_at,
            "team_display": project.get_assignment_team_display(),
            "can_submit": project.can_be_submitted_for_assignment(),
        }
        teams_data.append(team_info)

    # Calculate statistics
    total_enrolled = assignment.module.get_enrolled_students_count()
    students_in_teams_count = len(total_students_in_teams)
    students_without_teams = total_enrolled - students_in_teams_count

    # Get students who haven't joined any team yet
    unassigned_students = []
    if students_without_teams > 0:
        all_enrolled_students = StudentProfile.objects.filter(
            module_enrollments__module=assignment.module, module_enrollments__is_active=True
        ).select_related("user")

        for student in all_enrolled_students:
            if student.id not in total_students_in_teams:
                # Check if this student is eligible for this assignment
                if assignment.assignment_type == "direct":
                    is_assigned = DirectStudentAssignment.objects.filter(
                        assignment=assignment, student=student
                    ).exists()
                    if is_assigned:
                        unassigned_students.append(student)
                else:
                    unassigned_students.append(student)

    context = {
        "teacher": teacher,
        "assignment": assignment,
        "teams_data": teams_data,
        "total_teams": len(teams_data),
        "total_enrolled": total_enrolled,
        "students_in_teams_count": students_in_teams_count,
        "students_without_teams": students_without_teams,
        "unassigned_students": unassigned_students,
        "participation_rate": int(students_in_teams_count / total_enrolled * 100)
        if total_enrolled > 0
        else 0,
        "valid_teams": sum(1 for team in teams_data if team["is_valid_size"]),
        "submitted_teams": sum(
            1 for team in teams_data if team["status"] in ["submitted", "validated"]
        ),
    }

    return render(request, "teacher/assignments/teams.html", context)


@login_required
@transaction.atomic
def assignment_create(request):
    """Create a new project assignment - UPDATED TERMINOLOGY"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    # Get teacher's modules
    teacher_modules = Module.objects.filter(
        assignments__teacher=teacher, assignments__is_active=True, is_active=True
    ).distinct()

    if not teacher_modules.exists():
        messages.error(
            request, "Vous devez être assigné à au moins un module pour créer un devoir."
        )
        return redirect("teacher:assignments_dashboard")

    if request.method == "POST":
        form = ProjectAssignmentForm(request.POST, teacher=teacher)
        module_id = request.POST.get("module")

        # Get selected student IDs if it's a direct assignment
        selected_student_ids = request.POST.getlist("selected_student_ids")

        if form.is_valid() and module_id:
            try:
                module = teacher_modules.get(id=module_id)

                with transaction.atomic():
                    assignment = form.save(commit=False)
                    assignment.teacher = teacher
                    assignment.module = module
                    assignment.save()

                    # Direct assignments with hand-picked students: remember the choice now,
                    # without notifying anyone (it's still a draft). "All students"
                    # targets are resolved at publish time (sync_direct_targets).
                    if (
                        assignment.assignment_type == "direct"
                        and assignment.target_selection == "specific_students"
                    ):
                        chosen = StudentProfile.objects.filter(
                            id__in=selected_student_ids,
                            module_enrollments__module=module,
                            module_enrollments__is_active=True,
                        )
                        DirectStudentAssignment.objects.bulk_create(
                            [
                                DirectStudentAssignment(assignment=assignment, student=student)
                                for student in chosen
                            ]
                        )
                        if not chosen:
                            messages.warning(
                                request,
                                "Aucun étudiant sélectionné: choisissez-les avant de publier.",
                            )

                    messages.success(request, f"Devoir '{assignment.title}' créé avec succès.")

                    # Redirect based on assignment type
                    if assignment.assignment_type == "choice_based":
                        return redirect("teacher:assignment_options", assignment_id=assignment.id)
                    if assignment.target_selection == "specific_students":
                        return redirect("teacher:assignment_students", assignment_id=assignment.id)
                    else:
                        return redirect("teacher:assignment_detail", assignment_id=assignment.id)

            except Module.DoesNotExist:
                messages.error(request, "Module sélectionné invalide.")
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
        else:
            if not module_id:
                messages.error(request, "Veuillez sélectionner un module.")
    else:
        form = ProjectAssignmentForm(teacher=teacher)

    context = {
        "teacher": teacher,
        "form": form,
        "teacher_modules": teacher_modules,
        "selected_module": request.POST.get("module") or request.GET.get("module", ""),
    }

    return render(request, "teacher/assignments/create.html", context)


@login_required
@transaction.atomic
def assignment_options(request, assignment_id):
    """Manage project options for choice-based assignments"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    assignment = get_object_or_404(
        manageable_assignments(teacher), id=assignment_id, assignment_type="choice_based"
    )

    if request.method == "POST":
        form = ProjectOptionForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    option = form.save(commit=False)
                    option.assignment = assignment

                    # Set order automatically
                    max_order = (
                        assignment.project_options.aggregate(max_order=models.Max("order"))[
                            "max_order"
                        ]
                        or 0
                    )
                    option.order = max_order + 1

                    option.save()

                    messages.success(request, f"Option de projet '{option.title}' ajoutée.")
                    return redirect("teacher:assignment_options", assignment_id=assignment.id)

            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
    else:
        form = ProjectOptionForm()

    project_options = assignment.project_options.all().order_by("order")

    # Add statistics for each option using project system
    options_with_stats = []
    for option in project_options:
        # Count projects that selected this option
        projects_count = Project.objects.filter(
            project_assignment=assignment, selected_option=option
        ).count()

        options_with_stats.append(
            {
                "option": option,
                "projects_count": projects_count,  # Changed from groups_count
                "availability_status": option.get_availability_text(),
                "can_be_deleted": projects_count == 0,  # Can only delete if no projects selected it
            }
        )

    context = {
        "teacher": teacher,
        "assignment": assignment,
        "project_options": project_options,
        "options_with_stats": options_with_stats,
        "form": form,
    }

    return render(request, "teacher/assignments/options.html", context)


@login_required
@transaction.atomic
def assignment_students(request, assignment_id):
    """Select students for direct assignments"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    assignment = get_object_or_404(
        manageable_assignments(teacher), id=assignment_id, assignment_type="direct"
    )

    if request.method == "POST":
        form = StudentSelectionForm(request.POST, module=assignment.module)
        if form.is_valid():
            selected_students = form.cleaned_data["selected_students"]
            select_all = form.cleaned_data.get("select_all", False)

            try:
                with transaction.atomic():
                    if select_all or assignment.target_selection == "all_students":
                        # Assign to all students in module
                        enrolled_students = StudentProfile.objects.filter(
                            module_enrollments__module=assignment.module,
                            module_enrollments__is_active=True,
                        )
                        students_to_assign = enrolled_students
                    else:
                        # Assign to selected students
                        students_to_assign = selected_students

                    # Create direct assignments
                    created_count = 0
                    notification_batch = []

                    for student in students_to_assign:
                        direct_assignment, created = DirectStudentAssignment.objects.get_or_create(
                            assignment=assignment, student=student, defaults={"status": "assigned"}
                        )
                        if created:
                            created_count += 1

                            # Prepare notification for batch creation
                            notification_batch.append(
                                Notification(
                                    recipient=student,
                                    project_assignment=assignment,
                                    notification_type="assignment_created",
                                    message=f"Nouveau devoir assigné: {assignment.title}",
                                )
                            )

                    # Students only hear about it once the assignment is published
                    if notification_batch and assignment.status == "published":
                        Notification.objects.bulk_create(notification_batch)

                    messages.success(request, f"{created_count} étudiants assignés au devoir.")
                    return redirect("teacher:assignment_detail", assignment_id=assignment.id)

            except Exception:
                logger.exception("Erreur lors de l'assignation")
                messages.error(
                    request,
                    "Erreur lors de l'assignation. Réessayez ; si le problème persiste, contactez l'administration.",
                )
    else:
        form = StudentSelectionForm(module=assignment.module)

    # Get already assigned students
    assigned_students = DirectStudentAssignment.objects.filter(
        assignment=assignment
    ).select_related("student__user")

    # Get module enrollment statistics
    total_enrolled = assignment.module.get_enrolled_students_count()
    total_assigned = assigned_students.count()
    unassigned_count = total_enrolled - total_assigned

    context = {
        "teacher": teacher,
        "assignment": assignment,
        "form": form,
        "assigned_students": assigned_students,
        "total_enrolled": total_enrolled,
        "total_assigned": total_assigned,
        "unassigned_count": unassigned_count,
    }

    return render(request, "teacher/assignments/students.html", context)


@login_required
@transaction.atomic
def assignment_publish(request, assignment_id):
    """Publish an assignment"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    assignment = get_object_or_404(
        manageable_assignments(teacher), id=assignment_id, status="draft"
    )

    if request.method == "POST":
        try:
            with transaction.atomic():
                # "All students" direct assignments target whoever is enrolled right now
                assignment.sync_direct_targets()

                # Enhanced validation before publishing
                validation_errors = []

                # Check assignment completeness
                if not assignment.can_be_published():
                    if assignment.assignment_type == "choice_based":
                        if not assignment.project_options.exists():
                            validation_errors.append(
                                "Vous devez ajouter au moins une option de projet pour les devoirs à choix multiple."
                            )
                        else:
                            available_options = assignment.project_options.filter(
                                is_available=True
                            ).count()
                            if available_options == 0:
                                validation_errors.append(
                                    "Aucune option de projet n'est disponible."
                                )

                    if assignment.assignment_type == "direct":
                        if not assignment.direct_assignments.exists():
                            validation_errors.append(
                                "Vous devez assigner des étudiants avant de publier le devoir."
                            )

                # Check deadlines are still valid
                now = timezone.now()
                if assignment.deadline <= now:
                    validation_errors.append("La date limite de rendu doit être dans le futur.")

                if assignment.selection_deadline and assignment.selection_deadline <= now:
                    validation_errors.append(
                        "La date limite de sélection des projets doit être dans le futur."
                    )

                if validation_errors:
                    for error in validation_errors:
                        messages.error(request, error)
                    return redirect("teacher:assignment_detail", assignment_id=assignment.id)

                # Publish the assignment
                assignment.published_at = timezone.now()
                assignment.status = "published"
                assignment.save(update_fields=["published_at", "status"])

                # Optimized notification creation
                notification_batch = []

                if assignment.assignment_type == "direct":
                    # Notify assigned students
                    assigned_students = DirectStudentAssignment.objects.filter(
                        assignment=assignment
                    ).select_related("student")

                    for direct_assignment in assigned_students:
                        notification_batch.append(
                            Notification(
                                recipient=direct_assignment.student,
                                project_assignment=assignment,
                                notification_type="assignment_created",
                                message=f"Nouveau devoir disponible: {assignment.title}",
                            )
                        )
                else:
                    # Notify all students in module
                    enrolled_students = StudentProfile.objects.filter(
                        module_enrollments__module=assignment.module,
                        module_enrollments__is_active=True,
                    )

                    for student in enrolled_students:
                        notification_batch.append(
                            Notification(
                                recipient=student,
                                project_assignment=assignment,
                                notification_type="assignment_created",
                                message=f"Nouveau devoir disponible: {assignment.title}",
                            )
                        )

                # Batch create notifications
                if notification_batch:
                    Notification.objects.bulk_create(notification_batch)

                messages.success(request, f"Devoir '{assignment.title}' publié avec succès.")
                return redirect("teacher:assignment_detail", assignment_id=assignment.id)

        except Exception:
            logger.exception("Erreur lors de la publication")
            messages.error(
                request,
                "Erreur lors de la publication. Réessayez ; si le problème persiste, contactez l'administration.",
            )

    # Get assignment readiness information
    readiness_info = {
        "has_options": False,
        "has_students": False,
        "valid_deadlines": True,
        "total_students": 0,
        "total_options": 0,
    }

    if assignment.assignment_type == "choice_based":
        readiness_info["total_options"] = assignment.project_options.filter(
            is_available=True
        ).count()
        readiness_info["has_options"] = readiness_info["total_options"] > 0
    else:
        readiness_info["total_students"] = assignment.direct_assignments.count()
        readiness_info["has_students"] = readiness_info["total_students"] > 0

    # Check deadline validity
    now = timezone.now()
    readiness_info["valid_deadlines"] = assignment.deadline > now and (
        not assignment.selection_deadline or assignment.selection_deadline > now
    )

    context = {
        "teacher": teacher,
        "assignment": assignment,
        "readiness_info": readiness_info,
    }

    return render(request, "teacher/assignments/publish_confirm.html", context)


@login_required
def assignment_progress(request, assignment_id):
    """View detailed progress of an assignment"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    assignment = get_object_or_404(manageable_assignments(teacher), id=assignment_id)

    # Get submitted projects for this assignment with proper filtering
    submitted_projects = (
        assignment.submitted_projects.select_related("student__user")
        .prefetch_related("collaborators__user")
        .order_by("-updated_at")
    )

    # Apply filters
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("search", "")

    if status_filter:
        submitted_projects = submitted_projects.filter(status=status_filter)

    if search_query:
        submitted_projects = submitted_projects.filter(
            Q(title__icontains=search_query)
            | Q(student__user__first_name__icontains=search_query)
            | Q(student__user__last_name__icontains=search_query)
            | Q(student__user__username__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(submitted_projects, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Enhanced statistics calculation
    if assignment.assignment_type == "direct":
        total_expected = assignment.direct_assignments.count()
        assigned_count = assignment.direct_assignments.filter(status="assigned").count()
        started_count = assignment.direct_assignments.filter(status="started").count()
        submitted_count = assignment.direct_assignments.filter(status="submitted").count()
        validated_count = assignment.direct_assignments.filter(status="validated").count()
    else:
        # For choice-based assignments, count teams instead of groups
        total_projects = assignment.submitted_projects.count()
        total_expected = total_projects
        assigned_count = 0  # Not applicable for choice-based
        started_count = assignment.submitted_projects.filter(status="in_progress").count()
        submitted_count = assignment.submitted_projects.filter(status="submitted").count()
        validated_count = assignment.submitted_projects.filter(status="validated").count()

    completion_rate = int(validated_count / total_expected * 100) if total_expected > 0 else 0
    submission_rate = int(submitted_count / total_expected * 100) if total_expected > 0 else 0

    context = {
        "teacher": teacher,
        "assignment": assignment,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "search_query": search_query,
        # Drives the bulk-action bar: are there projects awaiting review?
        "has_submitted_projects": assignment.submitted_projects.filter(status="submitted").exists(),
        "total_expected": total_expected,
        "assigned_count": assigned_count,
        "started_count": started_count,
        "submitted_count": submitted_count,
        "validated_count": validated_count,
        "completion_rate": completion_rate,
        "submission_rate": submission_rate,
        "status_choices": Project.STATUS_CHOICES,
    }

    return render(request, "teacher/assignments/progress.html", context)


@login_required
def assignment_edit(request, assignment_id):
    """Edit assignment details"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    assignment = get_object_or_404(manageable_assignments(teacher), id=assignment_id)

    # Enhanced edit permissions check
    can_edit = assignment.status in ["draft", "published"]
    has_student_activity = False

    if assignment.status == "published":
        # Check if students have started working (using project system)
        has_student_activity = assignment.submitted_projects.exists()

        if has_student_activity:
            # Limited editing for published assignments with activity
            edit_type = "limited"
        else:
            edit_type = "full"
    else:
        edit_type = "full"

    if not can_edit:
        messages.error(request, "Ce devoir ne peut plus être modifié.")
        return redirect("teacher:assignment_detail", assignment_id=assignment.id)

    if request.method == "POST":
        # For limited editing, only allow certain fields
        if edit_type == "limited":
            assignment.description = request.POST.get("description", assignment.description)
            assignment.instructions = request.POST.get("instructions", assignment.instructions)
            try:
                assignment.save(update_fields=["description", "instructions"])
                messages.success(request, "Devoir mis à jour avec succès.")
                return redirect("teacher:assignment_detail", assignment_id=assignment.id)
            except Exception:
                logger.exception("Erreur lors de la mise à jour")
                messages.error(
                    request,
                    "Erreur lors de la mise à jour. Réessayez ; si le problème persiste, contactez l'administration.",
                )
        else:
            form = ProjectAssignmentForm(request.POST, instance=assignment, teacher=teacher)
            if form.is_valid():
                try:
                    assignment = form.save()
                    messages.success(request, "Devoir mis à jour avec succès.")
                    return redirect("teacher:assignment_detail", assignment_id=assignment.id)
                except ValidationError as e:
                    messages.error(request, " ".join(e.messages))
    else:
        if edit_type == "limited":
            form = None  # Will show simple form in template
        else:
            form = ProjectAssignmentForm(instance=assignment, teacher=teacher)

    context = {
        "teacher": teacher,
        "assignment": assignment,
        "form": form,
        "edit_type": edit_type,
        "has_student_activity": has_student_activity,
    }

    return render(request, "teacher/assignments/edit.html", context)


@login_required
@transaction.atomic
def option_delete(request, assignment_id, option_id):
    """Delete a project option"""
    teacher = get_teacher_or_error(request)
    if not teacher:
        return redirect("login")

    assignment = get_object_or_404(manageable_assignments(teacher), id=assignment_id)
    option = get_object_or_404(ProjectOption, id=option_id, assignment=assignment)

    # Enhanced deletion validation using project system
    projects_using_option = Project.objects.filter(selected_option=option).count()

    if projects_using_option > 0:
        messages.error(
            request,
            f"Cette option ne peut pas être supprimée car elle est utilisée par "
            f"{projects_using_option} projet(s).",
        )
        return redirect("teacher:assignment_options", assignment_id=assignment.id)

    if request.method == "POST":
        try:
            with transaction.atomic():
                option_title = option.title
                option.delete()

                messages.success(request, f"Option '{option_title}' supprimée avec succès.")
                return redirect("teacher:assignment_options", assignment_id=assignment.id)

        except Exception:
            logger.exception("Erreur lors de la suppression")
            messages.error(
                request,
                "Erreur lors de la suppression. Réessayez ; si le problème persiste, contactez l'administration.",
            )

    context = {
        "teacher": teacher,
        "assignment": assignment,
        "option": option,
        "projects_using_option": projects_using_option,
    }

    return render(request, "teacher/assignments/option_delete_confirm.html", context)
