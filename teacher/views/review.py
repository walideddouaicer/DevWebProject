import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import (
    get_project_for_teacher,
    teacher_required,
)
from student.models import Notification, Project

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

    context = {
        "teacher": teacher,
        "projects": projects,
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
    activities = project.activities.all().select_related("user")

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
        project.reject(by=request.teacher, reason=request.POST.get("reason", ""))
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
        project.request_revision(by=request.teacher, message=request.POST.get("content", ""))
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(
            request, f"Révision demandée pour « {project.title} ». L'équipe a été notifiée."
        )
    return redirect("teacher:project_review", project_id=project.id)


@login_required
def add_deliverable_comment(request, deliverable_id):
    """Teacher adds feedback on a specific deliverable"""
    from student.models import DeliverableComment, ProjectDeliverable

    deliverable = get_object_or_404(ProjectDeliverable, id=deliverable_id)
    project = deliverable.project

    if request.method != "POST":
        return redirect("teacher:project_review", project_id=project.id)

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    # Verify the deliverable belongs to a project in the teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(teacher=teacher, is_active=True).values_list(
        "module", flat=True
    )

    if project.module_id not in teacher_modules:
        messages.error(request, "Vous n'avez pas accès à ce projet.")
        return redirect("teacher:student_projects")

    content = request.POST.get("content", "").strip()
    if not content:
        messages.error(request, "Le commentaire ne peut pas être vide.")
        return redirect("teacher:project_review", project_id=project.id)

    DeliverableComment.objects.create(deliverable=deliverable, author=request.user, content=content)

    teacher_name = teacher.user.get_full_name() or teacher.user.username
    for member in project.get_team_members():
        Notification.objects.create(
            recipient=member,
            project=project,
            notification_type="deliverable",
            message=f"{teacher_name} a commenté le livrable '{deliverable.name}' du projet '{project.title}'",
        )

    messages.success(request, f"Commentaire ajouté sur le livrable '{deliverable.name}'.")
    return redirect("teacher:project_review", project_id=project.id)


@login_required
def add_teacher_comment(request, project_id):
    """Teacher adds a comment to a student project"""
    if request.method != "POST":
        return redirect("teacher:project_review", project_id=project_id)

    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "Vous n'avez pas de profil enseignant.")
        return redirect("login")

    # Get teacher's modules
    teacher_modules = ModuleAssignment.objects.filter(teacher=teacher, is_active=True).values_list(
        "module", flat=True
    )

    # Import here
    from student.models import ProjectComment

    project = get_object_or_404(Project, id=project_id, module__in=teacher_modules)

    content = request.POST.get("content")
    if content:
        try:
            # Create comment with teacher as author (now using User model)
            ProjectComment.objects.create(
                project=project,
                author=request.user,  # Now using User directly
                content=f"[FEEDBACK ENSEIGNANT]\n{content}",
            )

            # Notify student
            Notification.objects.create(
                recipient=project.student,
                project=project,
                notification_type="project_update",
                message=f"Nouveau commentaire de {teacher.user.get_full_name() or teacher.user.username} sur votre projet '{project.title}'",
            )

            # Notify collaborators too
            for collaborator in project.collaborators.all():
                Notification.objects.create(
                    recipient=collaborator,
                    project=project,
                    notification_type="project_update",
                    message=f"Nouveau commentaire de {teacher.user.get_full_name() or teacher.user.username} sur le projet '{project.title}'",
                )

            messages.success(request, "Commentaire ajouté avec succès.")
        except Exception:
            logger.exception("Erreur lors de l'ajout du commentaire")
            messages.error(
                request,
                "Erreur lors de l'ajout du commentaire. Réessayez ; si le problème persiste, contactez l'administration.",
            )
    else:
        messages.error(request, "Le commentaire ne peut pas être vide.")

    return redirect("teacher:project_review", project_id=project.id)


def _parse_score(raw):
    """Parse a /20 score; accepts French comma decimals. Returns Decimal or None."""
    from decimal import Decimal, InvalidOperation

    raw = (raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if not (0 <= value <= 20):
        return None
    return value


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
        score = _parse_score(request.POST.get("score"))
        comments = request.POST.get("comments", "").strip()
        validate_project = request.POST.get("validate_project") == "on"

        # Parse rubric rows (parallel arrays); empty rows are skipped
        names = request.POST.getlist("criterion_name")
        scores = request.POST.getlist("criterion_score")
        criterion_comments = request.POST.getlist("criterion_comment")

        criteria_rows = []
        errors = []
        if score is None:
            errors.append("La note globale est obligatoire et doit être comprise entre 0 et 20.")

        for i, name in enumerate(names):
            name = name.strip()
            raw_score = scores[i] if i < len(scores) else ""
            comment = (criterion_comments[i] if i < len(criterion_comments) else "").strip()
            if not name and not raw_score.strip():
                continue  # fully empty row
            crit_score = _parse_score(raw_score)
            if not name:
                errors.append(f"Le critère n°{i + 1} a une note mais pas de nom.")
            elif crit_score is None:
                errors.append(f"Le critère '{name}' doit avoir une note entre 0 et 20.")
            else:
                criteria_rows.append({"name": name, "score": crit_score, "comment": comment})

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
