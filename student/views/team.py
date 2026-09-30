import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from teacher.models import DirectStudentAssignment

from ..models import (
    CollaborationInvitation,
    Notification,
    Project,
    ProjectActivity,
    StudentProfile,
)
from ..utils import send_invitation_email

logger = logging.getLogger(__name__)


@login_required
def add_collaborator(request, project_id):
    """ENHANCED: Add collaborator with full assignment constraint checking"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_object_or_404(Project, id=project_id, student=student)

    # Only the project owner can add collaborators
    if project.student != student:
        messages.error(request, "Seul le propriétaire du projet peut ajouter des collaborateurs.")
        return redirect("student:project_detail", project_id=project.id)

    # Only in_progress projects can have collaborators added
    if project.status != "in_progress":
        messages.warning(
            request, "Vous ne pouvez ajouter des collaborateurs qu'aux projets en cours."
        )
        return redirect("student:project_detail", project_id=project.id)

    # Check assignment constraints
    if project.is_assignment_project():
        if not project.can_invite_more_collaborators():
            team_status = project.get_team_size_status()
            messages.error(
                request, f"Impossible d'ajouter des collaborateurs: {team_status['message']}"
            )
            return redirect("student:project_detail", project_id=project.id)

    if request.method == "POST":
        # Enhanced validation for assignment projects
        if project.is_assignment_project() and not project.project_assignment.is_team_work:
            messages.error(
                request, "Ce devoir doit être fait individuellement - aucun collaborateur autorisé."
            )
            return redirect("student:project_detail", project_id=project.id)

        # Check if at maximum capacity (before processing invitation)
        remaining_slots = project.get_remaining_team_slots()
        if remaining_slots <= 0:
            messages.warning(request, "Votre équipe a atteint la taille maximale autorisée.")
            return redirect("student:project_detail", project_id=project.id)

        collaborator_id = request.POST.get("collaborator")
        if collaborator_id:
            try:
                recipient = StudentProfile.objects.get(id=collaborator_id)

                # Check if already a collaborator
                if project.collaborators.filter(id=recipient.id).exists():
                    messages.info(request, f"{recipient} est déjà un collaborateur de ce projet.")
                    return redirect("student:project_detail", project_id=project.id)

                # For assignment projects, verify recipient eligibility
                if project.is_assignment_project():
                    assignment = project.project_assignment

                    # Check if recipient is enrolled in the module
                    if not recipient.module_enrollments.filter(
                        module=assignment.module, is_active=True
                    ).exists():
                        messages.error(
                            request,
                            f"{recipient} n'est pas inscrit au module {assignment.module.code}.",
                        )
                        return redirect("student:project_detail", project_id=project.id)

                    # For direct assignments, check if recipient is also assigned
                    if assignment.assignment_type == "direct":
                        if not DirectStudentAssignment.objects.filter(
                            assignment=assignment, student=recipient
                        ).exists():
                            messages.error(request, f"{recipient} n'est pas assigné à ce devoir.")
                            return redirect("student:project_detail", project_id=project.id)

                    # Check if recipient is already working on this assignment
                    existing_assignment_project = (
                        Project.objects.filter(project_assignment=assignment)
                        .filter(Q(student=recipient) | Q(collaborators=recipient))
                        .exclude(id=project.id)
                        .first()
                    )

                    if existing_assignment_project:
                        messages.error(
                            request,
                            f"{recipient} travaille déjà sur ce devoir dans un autre projet.",
                        )
                        return redirect("student:project_detail", project_id=project.id)

                # Use get_or_create to handle existing invitations
                invitation, created = CollaborationInvitation.objects.get_or_create(
                    project=project,
                    recipient=recipient,
                    defaults={"sender": student, "status": "pending", "message": ""},
                )

                if created:
                    # New invitation created
                    send_invitation_email(invitation)

                    # Assignment-specific notification message
                    if project.is_assignment_project():
                        notification_msg = (
                            f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                            f"sur le projet '{project.title}' pour le devoir '{project.project_assignment.title}'"
                        )
                    else:
                        notification_msg = (
                            f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                            f"sur le projet '{project.title}'"
                        )

                    messages.success(request, f"Invitation envoyée à {recipient}.")

                    # Create notification for the recipient
                    Notification.objects.create(
                        recipient=recipient,
                        project=project,
                        project_assignment=project.project_assignment,  # Link to assignment if exists
                        notification_type="invitation",
                        message=notification_msg,
                    )
                else:
                    # Invitation already exists - update it
                    if invitation.status == "pending":
                        messages.info(request, f"Une invitation a déjà été envoyée à {recipient}.")
                    else:
                        # Reactivate the invitation
                        invitation.status = "pending"
                        invitation.sender = student
                        invitation.message = ""
                        invitation.save()

                        send_invitation_email(invitation)
                        messages.success(request, f"Nouvelle invitation envoyée à {recipient}.")

                        # Create notification for the recipient
                        if project.is_assignment_project():
                            notification_msg = (
                                f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                                f"sur le projet '{project.title}' pour le devoir '{project.project_assignment.title}'"
                            )
                        else:
                            notification_msg = (
                                f"{student.user.get_full_name() or student.user.username} vous invite à collaborer "
                                f"sur le projet '{project.title}'"
                            )

                        Notification.objects.create(
                            recipient=recipient,
                            project=project,
                            project_assignment=project.project_assignment,
                            notification_type="invitation",
                            message=notification_msg,
                        )

            except StudentProfile.DoesNotExist:
                messages.error(request, "Étudiant non trouvé.")
            except Exception:
                logger.exception("Invitation failed")
                messages.error(
                    request, "L'invitation n'a pas pu être envoyée. Réessayez plus tard."
                )

    return redirect("student:project_detail", project_id=project.id)


@login_required
def invitations_list(request):
    """View to display pending collaboration invitations"""
    student = get_object_or_404(StudentProfile, user=request.user)

    # Get received invitations
    received_invitations = CollaborationInvitation.objects.filter(
        recipient=student, status="pending"
    )

    # Get sent invitations
    sent_invitations = CollaborationInvitation.objects.filter(sender=student, status="pending")

    context = {
        "received_invitations": received_invitations,
        "sent_invitations": sent_invitations,
    }

    return render(request, "student/invitations_list.html", context)


@login_required
@require_POST
def respond_to_invitation(request, invitation_id, response):
    """ENHANCED: Accept/reject invitation with assignment constraint validation"""
    student = get_object_or_404(StudentProfile, user=request.user)
    invitation = get_object_or_404(
        CollaborationInvitation, id=invitation_id, recipient=student, status="pending"
    )

    if response == "accept":
        # Additional validation for assignment projects
        project = invitation.project

        if project.is_assignment_project():
            assignment = project.project_assignment

            # Check if recipient can still join (assignment constraints)
            if not project.can_invite_more_collaborators():
                messages.error(request, "Cette équipe a atteint sa taille maximale.")
                invitation.status = "rejected"
                invitation.save()
                return redirect("student:invitations_list")

            # Check if recipient is already working on this assignment
            existing_assignment_project = (
                Project.objects.filter(project_assignment=assignment)
                .filter(Q(student=student) | Q(collaborators=student))
                .exclude(id=project.id)
                .first()
            )

            if existing_assignment_project:
                messages.error(
                    request,
                    f"Vous travaillez déjà sur ce devoir dans le projet '{existing_assignment_project.title}'.",
                )
                invitation.status = "rejected"
                invitation.save()
                return redirect("student:invitations_list")

            # Verify still enrolled in module
            if not student.module_enrollments.filter(
                module=assignment.module, is_active=True
            ).exists():
                messages.error(
                    request, f"Vous n'êtes plus inscrit au module {assignment.module.code}."
                )
                invitation.status = "rejected"
                invitation.save()
                return redirect("student:invitations_list")

            # For direct assignments, verify student is assigned
            if assignment.assignment_type == "direct":
                if not DirectStudentAssignment.objects.filter(
                    assignment=assignment, student=student
                ).exists():
                    messages.error(request, "Vous n'êtes pas assigné à ce devoir.")
                    invitation.status = "rejected"
                    invitation.save()
                    return redirect("student:invitations_list")

        # Proceed with standard acceptance using the enhanced method
        try:
            project.add_assignment_collaborator(student)
            invitation.status = "accepted"
            invitation.save()

            # Joined a team: stop advertising on the teammates board
            if project.is_assignment_project():
                from ..models import TeammateRequest

                TeammateRequest.objects.filter(
                    assignment=project.project_assignment, student=student
                ).update(is_active=False)

            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type="collaborator_added",
                description=f"{student.user.get_full_name() or student.user.username} a rejoint le projet en tant que collaborateur",
            )

            # Assignment-specific success message
            if project.is_assignment_project():
                messages.success(
                    request,
                    f"Vous avez rejoint l'équipe pour le projet '{project.title}' "
                    f"(devoir: {project.project_assignment.title}).",
                )
            else:
                messages.success(
                    request, f"Vous êtes maintenant collaborateur sur le projet '{project.title}'."
                )

        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            invitation.status = "rejected"
            invitation.save()

    elif response == "reject":
        invitation.status = "rejected"
        invitation.save()
        messages.info(
            request, f"Vous avez refusé l'invitation pour le projet '{invitation.project.title}'."
        )
    return redirect("student:invitations_list")


@login_required
def remove_collaborator(request, project_id, collaborator_id):
    student = get_object_or_404(StudentProfile, user=request.user)
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


@login_required
@require_POST
def cancel_invitation(request, invitation_id):
    student = get_object_or_404(StudentProfile, user=request.user)
    invitation = get_object_or_404(
        CollaborationInvitation, id=invitation_id, sender=student, status="pending"
    )

    project_id = invitation.project.id
    recipient_name = invitation.recipient

    # Delete the invitation
    invitation.delete()

    messages.success(request, f"L'invitation envoyée à {recipient_name} a été annulée.")
    return redirect("student:project_detail", project_id=project_id)
