import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import (
    get_project_for_teacher,
    teacher_required,
)
from ensa_project_manager.pagination import paginate
from student.forms import CommentForm
from student.models import (
    DeliverableComment,
    Notification,
    Project,
    ProjectComment,
    ProjectDeliverable,
)

from ..forms import EvaluationForm, RejectionForm, RevisionRequestForm, parse_rubric
from ..models import (
    Module,
    ModuleAssignment,
    TeacherProfile,
)

logger = logging.getLogger(__name__)

DEFAULT_EVALUATION_CRITERIA = [
    "Qualité technique",
    "Livrables & documentation",
    "Respect des délais",
    "Présentation & clarté",
]


@login_required
def student_projects(request):
    """View all student projects from teacher's modules"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    # Get all modules assigned to this teacher
    teacher_modules = ModuleAssignment.objects.filter(teacher=teacher, is_active=True).values_list(
        "module", flat=True
    )

    # Import here to avoid circular imports

    # Get projects from students in teacher's modules
    projects = (
        Project.objects.filter(module__in=teacher_modules)
        .select_related("student__user", "module")
        .prefetch_related("collaborators__user")
        .annotate(
            deliverable_count=Count("deliverables", distinct=True),
            collaborator_count=Count("collaborators", distinct=True),
        )
        .order_by("-updated_at")
    )

    # Filter by status if requested
    status_filter = request.GET.get("status", "")
    if status_filter:
        projects = projects.filter(status=status_filter)

    # Filter by module if requested
    module_filter = request.GET.get("module", "")
    if module_filter:
        projects = projects.filter(module__id=module_filter)

    # Get statistics
    total_projects = projects.count()
    submitted_projects = projects.filter(status="submitted").count()
    validated_projects = projects.filter(status="validated").count()
    rejected_projects = projects.filter(status="rejected").count()

    # Get teacher's modules for filter dropdown
    modules = Module.objects.filter(id__in=teacher_modules)

    page_obj = paginate(request, projects)
    context = {
        "teacher": teacher,
        "projects": page_obj,
        "page_obj": page_obj,
        "total_projects": total_projects,
        "submitted_projects": submitted_projects,
        "validated_projects": validated_projects,
        "rejected_projects": rejected_projects,
        "modules": modules,
        "status_filter": status_filter,
        "module_filter": module_filter,
    }

    return render(request, "teacher/student_projects.html", context)


@login_required
def project_review(request, project_id):
    """Detailed view for teacher to review a student project"""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    # Get teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(teacher=teacher, is_active=True).values_list(
        "module", flat=True
    )

    # Import here to avoid circular imports

    # Get project (only if it's in teacher's modules)
    project = get_object_or_404(
        Project.objects.select_related("student__user", "module"),
        id=project_id,
        module__in=teacher_modules,
    )

    # Get project details (deliverables grouped by name: latest + history)
    from student.utils import group_deliverables

    deliverables = group_deliverables(
        project.deliverables.all().prefetch_related("feedback_comments__author")
    )
    milestones = project.milestones.all()
    comments = project.comments.all().select_related(
        "author"
    )  # Fixed: now just 'author' since it's User
    activities = project.activities.select_related("user")[:50]

    context = {
        "teacher": teacher,
        "project": project,
        "deliverables": deliverables,
        "milestones": milestones,
        "comments": comments,
        "activities": activities,
        "evaluation": getattr(project, "evaluation", None),
    }

    return render(request, "teacher/project_review.html", context)


@teacher_required
@require_POST
def approve_project(request, project_id):
    """Teacher validates a submitted project of one of their modules."""
    project = get_project_for_teacher(request.teacher, project_id)
    try:
        project.validate(by=request.teacher)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, f"Projet « {project.title} » validé.")
    return redirect("teacher:project_review", project_id=project.id)


@teacher_required
@require_POST
def reject_project(request, project_id):
    """Teacher rejects a submitted project (optional reason in `reason`)."""
    project = get_project_for_teacher(request.teacher, project_id)
    try:
        form = RejectionForm(request.POST)
        reason = form.cleaned_data["reason"] if form.is_valid() else ""
        project.reject(by=request.teacher, reason=reason)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, f"Projet « {project.title} » rejeté. L'équipe a été notifiée.")
    return redirect("teacher:project_review", project_id=project.id)


@teacher_required
@require_POST
def request_revision(request, project_id):
    """Teacher asks for changes on a submitted project (message in `content`)."""
    project = get_project_for_teacher(request.teacher, project_id)
    try:
        form = RevisionRequestForm(request.POST)
        message = form.cleaned_data["content"] if form.is_valid() else ""
        project.request_revision(by=request.teacher, message=message)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(
            request, f"Révision demandée pour « {project.title} ». L'équipe a été notifiée."
        )
    return redirect("teacher:project_review", project_id=project.id)


@teacher_required
@require_POST
def add_deliverable_comment(request, deliverable_id):
    """Teacher adds feedback on a specific deliverable."""
    deliverable = get_object_or_404(
        ProjectDeliverable.objects.select_related("project"), pk=deliverable_id
    )
    project = get_project_for_teacher(request.teacher, deliverable.project_id)
    form = CommentForm(request.POST)
    if not form.is_valid():
        messages.error(request, " ".join(form.errors["content"]))
        return redirect("teacher:project_review", project_id=project.id)

    DeliverableComment.objects.create(
        deliverable=deliverable, author=request.user, content=form.cleaned_data["content"]
    )
    teacher_name = request.teacher.user.get_full_name() or request.teacher.user.username
    project.notify_team(
        f"{teacher_name} a commenté le livrable « {deliverable.name} » du projet « {project.title} ».",
        notification_type="deliverable",
    )
    messages.success(request, f"Commentaire ajouté sur le livrable « {deliverable.name} ».")
    return redirect("teacher:project_review", project_id=project.id)


@teacher_required
@require_POST
def add_teacher_comment(request, project_id):
    """Teacher adds a comment to a project of one of their modules."""
    project = get_project_for_teacher(request.teacher, project_id)
    form = CommentForm(request.POST)
    if not form.is_valid():
        messages.error(request, " ".join(form.errors["content"]))
        return redirect("teacher:project_review", project_id=project.id)

    ProjectComment.objects.create(
        project=project,
        author=request.user,
        content=f"[FEEDBACK ENSEIGNANT]\n{form.cleaned_data['content']}",
    )
    teacher_name = request.teacher.user.get_full_name() or request.teacher.user.username
    project.notify_team(f"Nouveau commentaire de {teacher_name} sur le projet « {project.title} ».")
    messages.success(request, "Commentaire ajouté avec succès.")
    return redirect("teacher:project_review", project_id=project.id)


@login_required
def grade_project(request, project_id):
    """Grade a project: overall score /20, appreciation, per-criterion rubric."""
    from student.models import ProjectActivity

    from ..models import EvaluationCriterion, ProjectEvaluation

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    teacher_modules = ModuleAssignment.objects.filter(teacher=teacher, is_active=True).values_list(
        "module", flat=True
    )

    project = get_object_or_404(
        Project.objects.select_related("student__user", "module"),
        id=project_id,
        module__in=teacher_modules,
    )

    if project.status not in ["submitted", "validated"]:
        messages.warning(request, "Seuls les projets soumis ou validés peuvent être notés.")
        return redirect("teacher:project_review", project_id=project.id)

    evaluation = getattr(project, "evaluation", None)
    teacher_name = teacher.user.get_full_name() or teacher.user.username

    if request.method == "POST":
        form = EvaluationForm(request.POST)
        criteria_rows, errors = parse_rubric(request.POST)
        if form.is_valid():
            score = form.cleaned_data["score"]
            comments = form.cleaned_data["comments"]
            validate_project = form.cleaned_data["validate_project"]
        else:
            errors = [e for field_errors in form.errors.values() for e in field_errors] + errors

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            is_new = evaluation is None
            if evaluation is None:
                evaluation = ProjectEvaluation(project=project)
            evaluation.teacher = teacher
            evaluation.score = score
            evaluation.comments = comments
            evaluation.save()

            # Rebuild the rubric to match the submitted rows
            evaluation.criteria.all().delete()
            for order, row in enumerate(criteria_rows):
                EvaluationCriterion.objects.create(
                    evaluation=evaluation,
                    name=row["name"],
                    score=row["score"],
                    comment=row["comment"],
                    order=order,
                )

            # Record activity
            ProjectActivity.objects.create(
                project=project,
                user=request.user,
                activity_type="status_changed",
                description=(
                    f"Projet noté {score}/20 par {teacher_name}"
                    if is_new
                    else f"Note mise à jour: {score}/20 par {teacher_name}"
                ),
            )

            # Optionally validate at the same time (same effects as approve_project)
            if validate_project and project.status == "submitted":
                project.validate(by=teacher)

            # Notify the whole team of the grade
            validated_note = (
                " et validé" if (validate_project and project.status == "validated") else ""
            )
            for member in project.get_team_members():
                Notification.objects.create(
                    recipient=member,
                    project=project,
                    notification_type="project_update",
                    message=(
                        f"Le projet '{project.title}' a été noté{validated_note}: "
                        f"{score}/20 ({evaluation.get_mention()}) par {teacher_name}"
                    ),
                )

            messages.success(request, f"Note enregistrée: {score}/20 ({evaluation.get_mention()}).")
            return redirect("teacher:project_review", project_id=project.id)

    # Build the rubric rows shown in the form
    if evaluation:
        existing_criteria = list(evaluation.criteria.all())
    else:
        existing_criteria = []

    if existing_criteria:
        criteria_for_form = [
            {"name": c.name, "score": c.score, "comment": c.comment} for c in existing_criteria
        ]
    else:
        criteria_for_form = [
            {"name": name, "score": "", "comment": ""} for name in DEFAULT_EVALUATION_CRITERIA
        ]

    context = {
        "teacher": teacher,
        "project": project,
        "evaluation": evaluation,
        "criteria_for_form": criteria_for_form,
    }

    return render(request, "teacher/grade_project.html", context)
