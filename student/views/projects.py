from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import (
    get_project_for_member,
    member_projects,
    student_required,
)

from ..forms import CommentForm, MakeProjectPublicForm, ProjectForm, QuickPublishForm
from ..models import (
    CollaborationInvitation,
    Notification,
    Project,
    ProjectActivity,
    ProjectComment,
    ProjectDeliverable,
    ProjectMilestone,
)


@student_required
@require_POST
def project_submit(request, project_id):
    """Owner submits the project for review (rules live in Project.submit)."""
    student = request.student
    project = get_project_for_member(student, project_id)
    try:
        project.submit(by=student)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, "Votre projet a été soumis avec succès.")
    return redirect("student:project_detail", project_id=project.id)


@student_required
@require_POST
def project_reopen(request, project_id):
    """Owner puts a rejected project back in progress."""
    student = request.student
    project = get_project_for_member(student, project_id)
    try:
        project.reopen(by=student)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, "Le projet est de nouveau en cours: vous pouvez le retravailler.")
    return redirect("student:project_detail", project_id=project.id)


@student_required
def dashboard(request):
    """What needs my attention (invitations, rework, deadlines), then all my projects."""
    from datetime import timedelta

    from teacher.models import ProjectAssignment

    student = request.student
    today = timezone.localdate()
    mine = member_projects(student)

    # Assignments that target me and that I haven't handed in yet
    done_assignment_ids = mine.filter(status__in=["submitted", "validated"]).values_list(
        "project_assignment_id", flat=True
    )
    enrolled = student.module_enrollments.filter(is_active=True).values_list("module_id", flat=True)
    upcoming = (
        ProjectAssignment.objects.filter(
            module_id__in=enrolled,
            status="published",
            deadline__gte=timezone.now(),
            deadline__lte=timezone.now() + timedelta(days=21),
        )
        .filter(Q(assignment_type="choice_based") | Q(direct_assignments__student=student))
        .exclude(id__in=done_assignment_ids)
        .select_related("module")
        .distinct()
        .order_by("deadline")[:6]
    )

    projects = (
        mine.select_related("module", "project_assignment", "student__user")
        .prefetch_related("collaborators__user")
        .order_by("-updated_at")
    )
    search_query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if search_query:
        projects = projects.filter(title__icontains=search_query)
    if status in dict(Project.STATUS_CHOICES):
        projects = projects.filter(status=status)

    counts = {
        row["status"]: row["n"]
        for row in mine.values("status").annotate(n=Count("id", distinct=True))
    }
    context = {
        "student": student,
        "today": today,
        "invitations": CollaborationInvitation.objects.filter(recipient=student, status="pending")
        .select_related("project", "sender__user")
        .order_by("-created_at")[:5],
        "to_rework": mine.filter(status__in=["revision_requested", "rejected"]).select_related(
            "module"
        ),
        "upcoming": upcoming,
        "projects": projects,
        "counts": counts,
        "total_projects": sum(counts.values()),
        "search_query": search_query,
        "status": status,
        "status_choices": Project.STATUS_CHOICES,
    }
    return render(request, "student/dashboard.html", context)


@student_required
def project_create(request):
    student = request.student

    if request.method == "POST":
        form = ProjectForm(request.POST, current_student=student)
        if form.is_valid():
            project = form.save(commit=False)
            project.student = student
            project.status = "in_progress"
            project.save()

            # This is needed to save many-to-many relationships
            form.save_m2m()

            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type="created",
                description="Projet créé",
            )

            messages.success(request, "Projet créé avec succès.")
            return redirect("student:project_detail", project_id=project.id)
    else:
        form = ProjectForm(current_student=student)

    context = {"form": form, "title": "Créer un nouveau projet"}

    return render(request, "student/project_form.html", context)


@student_required
def project_edit(request, project_id):
    student = request.student
    project = get_object_or_404(Project, id=project_id, student=student)

    # dont allow editing if the project is already validated
    if project.status == "validated":
        messages.warning(request, "Les projets validés ne peuvent plus être modifiés.")
        return redirect("student:project_detail", project_id=project.id)

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project, current_student=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Projet mis à jour avec succès.")
            return redirect("student:project_detail", project_id=project.id)
    else:
        form = ProjectForm(instance=project, current_student=student)

    context = {"form": form, "project": project, "title": "Modifier le projet"}

    return render(request, "student/project_form.html", context)


@student_required
def project_detail(request, project_id):
    """Enhanced project detail view with assignment context and team info"""
    student = request.student

    # Get the project with related data
    project = get_object_or_404(
        Project.objects.select_related("module", "project_assignment", "selected_option"),
        id=project_id,
    )

    # Check if the requesting user is either the owner or a collaborator
    is_owner = project.student == student
    is_collaborator = project.collaborators.filter(id=student.id).exists()

    # If the user is neither, deny access
    if not is_owner and not is_collaborator:
        messages.error(request, "Vous n'avez pas l'autorisation de voir ce projet.")
        return redirect("student:dashboard")

    # Get basic project data (deliverables grouped by name: latest + history)
    from ..utils import group_deliverables

    deliverables = group_deliverables(
        ProjectDeliverable.objects.filter(project=project).prefetch_related(
            "feedback_comments__author"
        )
    )
    milestones = ProjectMilestone.objects.filter(project=project)
    project_activities = ProjectActivity.objects.filter(project=project).select_related("user")[:50]
    comments = project.comments.all().select_related("author")

    # Assignment-specific context
    assignment_context = {}
    if project.is_assignment_project():
        assignment = project.project_assignment
        team_info = project.get_assignment_team_info()

        assignment_context = {
            "assignment": assignment,
            "is_assignment_project": True,
            "assignment_type": assignment.assignment_type,
            "team_info": team_info,
            "selected_option": project.selected_option,
            "deadline_info": {
                "assignment_deadline": assignment.deadline,
                "is_overdue": project.is_overdue(),
                "can_submit": project.can_be_submitted_for_assignment(),
            },
        }
    else:
        assignment_context = {
            "is_assignment_project": False,
            "team_info": {
                "team_members": project.get_team_members(),
                "team_size": project.get_team_size(),
                "size_status": {
                    "status": "unlimited",
                    "message": "Projet personnel",
                    "can_invite": True,
                },
                "display_name": None,
            },
        }

    # Invite picker: a short list when few candidates, search (invite_candidates) otherwise
    candidates = (
        project.invite_candidates() if is_owner and project.status == "in_progress" else None
    )
    candidate_count = candidates.count() if candidates is not None else 0
    available_students = (
        candidates.order_by("user__last_name")[:30]
        if candidates is not None and candidate_count <= 30
        else []
    )

    # For project owners, show pending invitations
    pending_invitations = []
    if is_owner:
        pending_invitations = CollaborationInvitation.objects.filter(
            project=project, status="pending"
        ).select_related("recipient__user")

    # Assignment-specific action buttons
    available_actions = {
        "can_edit": is_owner and project.status not in ["validated"],
        "can_delete": is_owner
        and project.status == "in_progress"
        and not project.is_assignment_project(),
        "can_submit": is_owner and project.status in ["in_progress", "revision_requested"],
        "can_invite_collaborators": (
            is_owner
            and project.status == "in_progress"
            and assignment_context.get("team_info", {})
            .get("size_status", {})
            .get("can_invite", True)
        ),
        "can_add_deliverables": (is_owner or is_collaborator) and project.status != "validated",
        "can_add_milestones": (is_owner or is_collaborator) and project.status != "validated",
        "can_comment": True,  # Everyone can comment
    }

    # Assignment submission validation
    if project.is_assignment_project():
        available_actions["can_submit"] = is_owner and project.can_be_submitted_for_assignment()
        if not available_actions["can_submit"] and is_owner:
            # Provide specific reason why can't submit
            team_status = project.get_team_size_status()
            if team_status["status"] in ["too_small", "too_large"]:
                available_actions["submit_blocked_reason"] = team_status["message"]
            elif not project.is_team_size_valid():
                available_actions["submit_blocked_reason"] = "Taille d'équipe invalide"
            elif project.is_overdue():
                available_actions["submit_blocked_reason"] = "Date limite dépassée"

    context = {
        "project": project,
        "deliverables": deliverables,
        "collaborators": project.collaborators.all(),
        "milestones": milestones,
        "available_students": available_students,
        "candidate_count": candidate_count,
        "pending_invitations": pending_invitations,
        "is_owner": is_owner,
        "is_collaborator": is_collaborator,
        "project_activities": project_activities,
        "comments": comments,
        "assignment_context": assignment_context,  # ENHANCED
        "available_actions": available_actions,  # ENHANCED
        "evaluation": getattr(project, "evaluation", None),  # Teacher grade (if any)
    }

    return render(request, "student/project_detail.html", context)


@student_required
def project_delete(request, project_id):
    """View to delete a project"""
    student = request.student
    project = get_object_or_404(Project, id=project_id, student=student)

    # Only allow deletion of projects that are in progress (not submitted, validated, or rejected)
    if project.status != "in_progress":
        messages.warning(request, "Seuls les projets en cours peuvent être supprimés.")
        return redirect("student:project_detail", project_id=project.id)

    if request.method == "POST":
        # Delete any deliverables associated with this project
        ProjectDeliverable.objects.filter(project=project).delete()

        # Also delete any pending invitations for this project
        CollaborationInvitation.objects.filter(project=project).delete()

        # Delete any milestones associated with this project
        ProjectMilestone.objects.filter(project=project).delete()

        # Delete any comments associated with this project
        ProjectComment.objects.filter(project=project).delete()

        # Delete any activities associated with this project
        ProjectActivity.objects.filter(project=project).delete()

        # Delete any notifications associated with this project
        Notification.objects.filter(project=project).delete()

        # Delete the project itself
        project.delete()

        messages.success(request, "Le projet a été supprimé avec succès.")
        return redirect("student:dashboard")

    context = {
        "project": project,
    }

    return render(request, "student/project_delete_confirm.html", context)


@student_required
def add_comment(request, project_id):
    student = request.student
    project = get_project_for_member(student, project_id)

    if request.method == "POST":
        form = CommentForm(request.POST)
        content = form.cleaned_data["content"] if form.is_valid() else ""
        if content:
            comment = ProjectComment(
                project=project,
                author=request.user,  # Now using User directly instead of StudentProfile
                content=content,
            )
            comment.save()

            # Add activity record
            activity = ProjectActivity(
                project=project,
                user=request.user,
                activity_type="comment_added",
                description=f'A ajouté un commentaire: "{content[:50]}{"..." if len(content) > 50 else ""}"',
            )
            activity.save()

            messages.success(request, "Commentaire ajouté avec succès.")
        else:
            for error in form.errors.get("content", ["Le commentaire ne peut pas être vide."]):
                messages.error(request, error)

    return redirect("student:project_detail", project_id=project.id)


@student_required
def make_project_public(request, project_id):
    """Student makes their project public (instant, no approval needed)"""
    student = request.student
    project = get_object_or_404(Project, id=project_id, student=student)

    if not project.can_be_made_public():
        messages.error(request, "Ce projet ne peut pas être rendu public. Il doit être validé.")
        return redirect("student:project_detail", project_id=project.id)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "quick_publish":
            # Quick publish with current content
            form = QuickPublishForm(request.POST)
            if form.is_valid():
                if project.make_public():
                    ProjectActivity.objects.create(
                        project=project,
                        user=request.user,
                        activity_type="made_public",
                        description="Projet rendu public",
                    )
                    messages.success(
                        request,
                        f"Votre projet « {project.title} » est maintenant visible sur la vitrine.",
                    )
                    return redirect("public:project_detail", project_id=project.id)

        elif action == "enhanced_publish":
            # Publish with enhanced content
            form = MakeProjectPublicForm(request.POST, request.FILES, instance=project)
            if form.is_valid():
                # Save the enhanced fields first
                enhanced_project = form.save(commit=False)

                # Then make it public
                if enhanced_project.make_public():
                    # Now save all the enhanced fields to the database
                    enhanced_project.save()

                    # Save selected showcase tags (custom through-model field)
                    form.save_showcase_tags(enhanced_project)

                    ProjectActivity.objects.create(
                        project=enhanced_project,
                        user=request.user,
                        activity_type="made_public",
                        description="Projet rendu public avec contenu enrichi",
                    )
                    messages.success(
                        request,
                        f"Votre projet « {enhanced_project.title} » est maintenant visible sur la vitrine.",
                    )
                    return redirect("public:project_detail", project_id=enhanced_project.id)
                else:
                    messages.error(request, "Erreur lors de la publication du projet.")
            else:
                # Form has errors, show them
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Erreur dans {field}: {error}")

    # GET request - show both options
    quick_form = QuickPublishForm()
    enhanced_form = MakeProjectPublicForm(instance=project)

    context = {
        "project": project,
        "quick_form": quick_form,
        "enhanced_form": enhanced_form,
    }

    return render(request, "student/make_project_public.html", context)


@student_required
def make_project_private(request, project_id):
    """Student removes their project from public showcase"""
    student = request.student
    project = get_object_or_404(Project, id=project_id, student=student, is_public=True)

    if request.method == "POST":
        project.make_private()

        ProjectActivity.objects.create(
            project=project,
            user=request.user,
            activity_type="made_private",
            description="Projet retiré de l'affichage public",
        )

        messages.success(
            request, f"Votre projet '{project.title}' n'est plus visible publiquement."
        )
        return redirect("student:project_detail", project_id=project.id)

    context = {"project": project}
    return render(request, "student/make_project_private_confirm.html", context)


@student_required
def project_submit_confirmation(request, project_id):
    """Show confirmation page before project submission"""
    student = request.student
    project = get_project_for_member(student, project_id)

    # Only the owner can submit
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut le soumettre.")
        return redirect("student:project_detail", project_id=project.id)

    if project.status not in ["in_progress", "revision_requested"]:
        messages.warning(request, "Seuls les projets en cours ou en révision peuvent être soumis.")
        return redirect("student:project_detail", project_id=project.id)

    # Get pending invitations to show in confirmation
    pending_invitations = CollaborationInvitation.objects.filter(
        project=project, status="pending"
    ).select_related("recipient__user")

    # Get project statistics for the checklist
    deliverables_count = project.deliverables.values("name").distinct().count()
    milestones_count = project.milestones.count()
    completed_milestones_count = project.milestones.filter(completed=True).count()

    context = {
        "project": project,
        "pending_invitations": pending_invitations,
        "deliverables_count": deliverables_count,
        "milestones_count": milestones_count,
        "completed_milestones_count": completed_milestones_count,
        "blockers": project.get_submission_blockers(),
    }

    return render(request, "student/project_submit_confirmation.html", context)
