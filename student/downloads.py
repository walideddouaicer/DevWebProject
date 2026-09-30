"""Permission-checked deliverable downloads (PLAN P1.7).

Who may download a deliverable:
- anyone, if the project is on the public showcase AND its owner opted in to public files;
- the project's team (owner + collaborators);
- teachers of the project's module;
- administrators.
Everyone else gets a 404 (we don't reveal that the file exists).
"""

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from accounts.permissions import get_profiles, member_projects, teacher_module_ids

from .models import ProjectDeliverable

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


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
    if inline and extension in IMAGE_EXTENSIONS:
        # Images shown inline can't run anything; PDFs need the browser's viewer,
        # which a CSP sandbox would block.
        response["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'"
    return response
