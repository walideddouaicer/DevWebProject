import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import get_project_for_owner, student_required

from ..models import (
    CollaborationInvitation,
    Project,
    StudentProfile,
)

logger = logging.getLogger(__name__)


@student_required
@require_POST
def add_collaborator(request, project_id):
    """Owner invites a student to the team (rules live in Project.invite)."""
    project = get_object_or_404(Project, id=project_id, student=request.student)
    recipient = get_object_or_404(StudentProfile, id=request.POST.get("collaborator") or 0)
    try:
        project.invite(by=request.student, recipient=recipient)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, f"Invitation envoyée à {recipient.get_full_name()}.")
    return redirect("student:project_detail", project_id=project.id)


@student_required
def invitations_list(request):
    """View to display pending collaboration invitations"""
    student = request.student

    # Get received invitations
    received_invitations = CollaborationInvitation.objects.filter(
        recipient=student, status="pending"
    ).select_related("project__project_assignment", "project__module", "sender__user")

    # Get sent invitations
    sent_invitations = CollaborationInvitation.objects.filter(
        sender=student, status="pending"
    ).select_related("project", "recipient__user")

    context = {
        "received_invitations": received_invitations,
        "sent_invitations": sent_invitations,
    }

    return render(request, "student/invitations_list.html", context)


@student_required
@require_POST
def respond_to_invitation(request, invitation_id, response):
    """Accept or decline an invitation (rules live in CollaborationInvitation.accept)."""
    invitation = get_object_or_404(
        CollaborationInvitation.objects.select_related("project"),
        id=invitation_id,
        recipient=request.student,
        status="pending",
    )
    project = invitation.project
    if response == "accept":
        try:
            invitation.accept()
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, f"Vous avez rejoint l'équipe du projet « {project.title} ».")
            return redirect("student:project_detail", project_id=project.id)
    elif response == "reject":
        invitation.decline()
        messages.info(request, f"Invitation au projet « {project.title} » refusée.")
    return redirect("student:invitations_list")


@student_required
@require_POST
def remove_collaborator(request, project_id, collaborator_id):
    student = request.student
    project = get_object_or_404(Project, id=project_id, student=student)

    # Only project owner can remove collaborators
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut retirer des collaborateurs.")
        return redirect("student:project_detail", project_id=project.id)

    # Verify the project is in draft status
    if project.status != "in_progress":
        messages.warning(
            request, "Les collaborateurs ne peuvent être retirés que pour les projets en cours."
        )
        return redirect("student:project_detail", project_id=project.id)

    try:
        collaborator = StudentProfile.objects.get(id=collaborator_id)

        # Use the assignment-aware removal method
        project.remove_assignment_collaborator(collaborator)
        messages.success(request, f"{collaborator} a été retiré des collaborateurs du projet.")

    except StudentProfile.DoesNotExist:
        messages.error(request, "Étudiant non trouvé.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))

    return redirect("student:project_detail", project_id=project.id)


@student_required
@require_POST
def cancel_invitation(request, invitation_id):
    student = request.student
    invitation = get_object_or_404(
        CollaborationInvitation, id=invitation_id, sender=student, status="pending"
    )

    project_id = invitation.project.id
    recipient_name = invitation.recipient

    # Delete the invitation
    invitation.delete()

    messages.success(request, f"L'invitation envoyée à {recipient_name} a été annulée.")
    return redirect("student:project_detail", project_id=project_id)


@student_required
def invite_candidates(request, project_id):
    """Search students the owner can invite (HTMX partial; full page without JS)."""
    project = get_project_for_owner(request.student, project_id)
    query = request.GET.get("q", "").strip()
    results = []
    if project.status == "in_progress" and len(query) >= 2:
        results = (
            project.invite_candidates()
            .filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__username__icontains=query)
                | Q(student_id__icontains=query)
            )
            .order_by("user__last_name")[:8]
        )
    context = {"project": project, "results": results, "query": query}
    template = (
        "student/partials/invite_results.html" if request.htmx else "student/invite_search.html"
    )
    return render(request, template, context)
