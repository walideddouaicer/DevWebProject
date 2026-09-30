from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import (
    get_project_for_member,
    student_required,
)

from ..forms import (
    MilestoneForm,
)
from ..models import (
    Project,
    ProjectActivity,
    ProjectMilestone,
)


@student_required
def add_milestone(request, project_id):
    student = request.student
    project = get_project_for_member(student, project_id)

    if request.method == "POST":
        form = MilestoneForm(request.POST)
        if form.is_valid():
            milestone = form.save(commit=False)
            milestone.project = project
            milestone.save()

            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type="milestone_added",
                description=f"Jalon ajouté: {milestone.title}",
            )

            messages.success(request, "Jalon ajouté avec succès.")
            return redirect("student:project_detail", project_id=project.id)
    else:
        form = MilestoneForm()

    context = {"form": form, "project": project, "title": "Ajouter un jalon"}

    return render(request, "student/milestone_form.html", context)


@student_required
@require_POST
def toggle_milestone(request, milestone_id):
    student = request.student
    milestone = get_object_or_404(
        ProjectMilestone,
        id=milestone_id,
        project__in=Project.objects.filter(Q(student=student) | Q(collaborators=student)),
    )

    # Toggle completed status
    if milestone.completed:
        # Undo completion
        milestone.completed = False
        milestone.completed_by = None
        milestone.completed_at = None
        milestone.save()

        messages.success(request, f"Le jalon '{milestone.title}' a été marqué comme non complété.")
    else:
        # Mark as completed
        milestone.completed = True
        milestone.completed_by = request.user
        milestone.completed_at = timezone.now()
        milestone.save()

        # Add activity
        ProjectActivity.objects.create(
            project=milestone.project,
            user=request.user,
            activity_type="milestone_completed",
            description=f"Jalon '{milestone.title}' marqué comme complété",
        )

        messages.success(request, f"Le jalon '{milestone.title}' a été marqué comme complété.")

    return redirect("student:project_detail", project_id=milestone.project.id)
