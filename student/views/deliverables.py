from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from accounts.permissions import (
    get_profiles,
    get_project_for_member,
    member_projects,
    teacher_module_ids,
)

from ..forms import CommentForm, DeliverableForm
from ..models import (
    Notification,
    ProjectActivity,
    ProjectDeliverable,
    StudentProfile,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@login_required
def upload_deliverable(request, project_id):
    """View to upload a deliverable file for a project"""
    student = get_object_or_404(StudentProfile, user=request.user)
    project = get_project_for_member(student, project_id)

    # Don't allow uploads for validated projects
    if project.status == "validated":
        messages.warning(request, "Impossible d'ajouter des livrables à un projet validé.")
        return redirect("student:project_detail", project_id=project.id)

    if request.method == "POST":
        form = DeliverableForm(request.POST, request.FILES)
        if form.is_valid():
            deliverable = form.save(commit=False)
            deliverable.project = project
            # Same name on the same project = new version (v1, v2, ...)
            deliverable.version = ProjectDeliverable.next_version(project, deliverable.name)
            deliverable.save()

            # Record activity
            version_note = f" (v{deliverable.version})" if deliverable.version > 1 else ""
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type="deliverable_added",
                description=f"Livrable ajouté: {deliverable.name}{version_note}",
            )

            if deliverable.version > 1:
                messages.success(
                    request,
                    f"Nouvelle version (v{deliverable.version}) de '{deliverable.name}' ajoutée.",
                )
            else:
                messages.success(request, "Le livrable a été ajouté avec succès.")
            return redirect("student:project_detail", project_id=project.id)
    else:
        form = DeliverableForm()

    context = {"form": form, "project": project, "title": "Ajouter un livrable"}

    return render(request, "student/upload_deliverable.html", context)


@login_required
def add_deliverable_comment(request, deliverable_id):
    """Student replies to feedback on a specific deliverable"""
    from ..models import DeliverableComment

    student = get_object_or_404(StudentProfile, user=request.user)
    deliverable = get_object_or_404(ProjectDeliverable, id=deliverable_id)
    project = deliverable.project

    # Only team members can comment on a deliverable
    is_owner = project.student == student
    is_collaborator = project.collaborators.filter(id=student.id).exists()
    if not is_owner and not is_collaborator:
        messages.error(request, "Vous n'avez pas l'autorisation de commenter ce livrable.")
        return redirect("student:dashboard")

    if request.method == "POST":
        form = CommentForm(request.POST)
        content = form.cleaned_data["content"] if form.is_valid() else ""
        if content:
            DeliverableComment.objects.create(
                deliverable=deliverable, author=request.user, content=content
            )

            # Notify the rest of the team
            for member in project.get_team_members():
                if member != student:
                    Notification.objects.create(
                        recipient=member,
                        project=project,
                        notification_type="deliverable",
                        message=f"{student.get_full_name()} a répondu sur le livrable '{deliverable.name}' du projet '{project.title}'",
                    )

            messages.success(request, "Votre réponse a été ajoutée.")
        else:
            messages.error(request, "Le commentaire ne peut pas être vide.")

    return redirect("student:project_detail", project_id=project.id)


def can_download(user, project):
    if (
        project.is_public
        and project.public_deliverables
        and not project.is_hidden_by_admin
        and project.status == "validated"
    ):
        return True
    if not user.is_authenticated:
        return False
    profiles = get_profiles(user)
    if profiles["admin"]:
        return True
    if profiles["teacher"] and project.module_id in teacher_module_ids(profiles["teacher"]):
        return True
    if profiles["student"]:
        return member_projects(profiles["student"]).filter(pk=project.pk).exists()
    return False


@require_GET
def deliverable_download(request, deliverable_id):
    deliverable = get_object_or_404(
        ProjectDeliverable.objects.select_related("project"), pk=deliverable_id
    )
    if not can_download(request.user, deliverable.project):
        raise Http404
    try:
        handle = deliverable.file.open("rb")
    except FileNotFoundError:
        raise Http404

    inline = request.GET.get("inline") == "1" and deliverable.is_previewable
    extension = deliverable.extension
    filename = f"{slugify(deliverable.name) or 'livrable'}-v{deliverable.version}{extension}"
    response = FileResponse(handle, as_attachment=not inline, filename=filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=0"
    response["Referrer-Policy"] = "no-referrer"
    if inline:
        # The project page previews PDFs/images in an iframe: allow same-origin framing.
        response["X-Frame-Options"] = "SAMEORIGIN"
        response._csp_replace = response._csp_replace_ro = {"frame-ancestors": ["'self'"]}
    if inline and extension in IMAGE_EXTENSIONS:
        # Images shown inline can't run anything; PDFs need the browser's viewer,
        # which a CSP sandbox would block.
        response["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'"
    return response
