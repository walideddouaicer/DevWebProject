# public/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

# Import forms
from student.forms import ProjectReportForm, PublicCommentForm

# Import models
from student.models import (
    Project,
    ProjectLike,
    ProjectView,
    ShowcaseTag,
    StudentProfile,
)
from teacher.models import TeacherProfile


def _public_comments(project):
    return (
        project.public_comments.filter(is_flagged=False)
        .select_related("author")
        .order_by("-created_at")[:50]
    )


def public_projects():
    """Projects visible on the showcase: published, validated, not hidden by moderation."""
    return Project.objects.filter(is_public=True, is_hidden_by_admin=False, status="validated")


def get_public_project(project_id):
    return get_object_or_404(public_projects(), pk=project_id)


def get_common_context():
    """Get common context data for all public pages"""

    # Get popular public projects for the featured section
    featured_projects = (
        Project.objects.filter(is_public=True, is_hidden_by_admin=False, status="validated")
        .select_related("student__user", "module")
        .prefetch_related("showcase_tags__tag")
        .order_by("-like_count", "-view_count", "-made_public_at")[:6]
    )  # Get 8 popular projects

    return {
        "total_projects": public_projects().count(),
        "total_students": StudentProfile.objects.count(),
        "total_teachers": TeacherProfile.objects.count(),
        "featured_projects": featured_projects,
    }


def homepage(request):
    """Landing page with app presentation and auth links"""
    context = get_common_context()
    return render(request, "public/homepage.html", context)


def features(request):
    """Former marketing page, merged into "À propos"."""
    return redirect("public:about", permanent=True)


def about(request):
    """About ENSA Project Manager page"""
    context = get_common_context()
    return render(request, "public/about.html", context)


def public_projects_showcase(request):
    """Main showcase page - accessible from homepage 'Projects' button"""

    # Get all public projects (no admin approval needed!)
    projects = (
        public_projects()
        .select_related("student__user", "module")
        .prefetch_related("showcase_tags__tag")
    )

    # Apply search filter
    search_query = request.GET.get("search", "")
    if search_query:
        projects = projects.filter(
            Q(title__icontains=search_query)
            | Q(public_description__icontains=search_query)
            | Q(description__icontains=search_query)  # Fallback to main description
            | Q(technologies__icontains=search_query)
            | Q(student__user__first_name__icontains=search_query)
            | Q(student__user__last_name__icontains=search_query)
        )

    # Filter by tag
    tag_filter = request.GET.get("tag", "")
    if tag_filter:
        projects = projects.filter(showcase_tags__tag__name=tag_filter)

    # Filter by project type
    type_filter = request.GET.get("type", "")
    if type_filter:
        projects = projects.filter(project_type=type_filter)

    # Enhanced filtering
    has_demo = request.GET.get("has_demo", "")
    if has_demo:
        projects = projects.exclude(public_demo_url="")

    has_github = request.GET.get("has_github", "")
    if has_github:
        projects = projects.exclude(public_github_url="")

    # Sorting options
    sort_by = request.GET.get("sort", "recent")
    if sort_by == "popular":
        projects = projects.order_by("-like_count", "-view_count")
    elif sort_by == "views":
        projects = projects.order_by("-view_count")
    elif sort_by == "likes":
        projects = projects.order_by("-like_count")
    elif sort_by == "title":
        projects = projects.order_by("title")
    else:  # recent
        projects = projects.order_by("-made_public_at")

    # Pagination
    paginator = Paginator(projects, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get filter options
    available_tags = (
        ShowcaseTag.objects.annotate(project_count=Count("projectshowcasetag"))
        .filter(project_count__gt=0)
        .order_by("name")
    )

    # Statistics
    total_projects = projects.count()
    projects_with_demo = projects.exclude(public_demo_url="").count()
    projects_with_github = projects.exclude(public_github_url="").count()

    context = {
        "page_obj": page_obj,
        "available_tags": available_tags,
        "project_types": Project.PROJECT_TYPES,
        "search_query": search_query,
        "tag_filter": tag_filter,
        "type_filter": type_filter,
        "sort_by": sort_by,
        "has_demo": has_demo,
        "has_github": has_github,
        "total_projects": total_projects,
        "projects_with_demo": projects_with_demo,
        "projects_with_github": projects_with_github,
    }

    return render(request, "public/projects_showcase.html", context)


def public_project_detail(request, project_id):
    """Detailed view of a public project - includes deliverables!"""

    project = get_object_or_404(
        public_projects().select_related("student__user", "module"), pk=project_id
    )

    # Track view (only once per session per project)
    view_key = f"viewed_project_{project_id}"
    if not request.session.get(view_key):
        ProjectView.objects.create(
            project=project,
            user=request.user if request.user.is_authenticated else None,
            ip_address=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        # Atomic increment (concurrent visitors must not lose counts)
        Project.objects.filter(pk=project.pk).update(view_count=F("view_count") + 1)
        project.view_count += 1

        # Mark as viewed in session
        request.session[view_key] = True

    # Get deliverables, grouped by name (latest version of each)
    from student.utils import group_deliverables

    # Files are private unless the owner opted in when publishing
    deliverables = (
        group_deliverables(project.deliverables.all()) if project.public_deliverables else []
    )

    comments = _public_comments(project)

    # Get milestones for additional context
    milestones = project.milestones.all().order_by("due_date")

    # Get collaborators
    collaborators = project.collaborators.all().select_related("user")

    # Check user interactions
    user_has_liked = False
    can_report = False
    has_already_reported = False

    if request.user.is_authenticated:
        user_has_liked = project.public_likes.filter(user=request.user).exists()
        # Check if user has already reported this project
        has_already_reported = project.reports.filter(reporter=request.user).exists()
        # Can report if user hasn't already reported this project
        can_report = not project.reports.filter(reporter=request.user).exists()

    # Related projects (same type or same student)
    related_projects = (
        public_projects()
        .filter(Q(project_type=project.project_type) | Q(student=project.student))
        .select_related("student__user")
        .prefetch_related("showcase_tags__tag")
        .exclude(id=project.id)
        .order_by("-like_count")[:4]
    )

    # Comment form for authenticated users
    comment_form = None
    if request.user.is_authenticated:
        comment_form = PublicCommentForm()

    context = {
        "project": project,
        "deliverables": deliverables,  # Include deliverables in public view!
        "milestones": milestones,
        "collaborators": collaborators,
        "comments": comments,
        "related_projects": related_projects,
        "user_has_liked": user_has_liked,
        "can_report": can_report,
        "has_already_reported": has_already_reported,
        "comment_form": comment_form,
    }

    return render(request, "public/project_detail.html", context)


@login_required
@require_POST
def toggle_project_like(request, project_id):
    """Like/unlike a showcased project. HTMX gets the button back, scripts get JSON,
    plain forms are redirected (works without JavaScript)."""
    project = get_public_project(project_id)
    like, created = ProjectLike.objects.get_or_create(project=project, user=request.user)
    if not created:
        like.delete()
    project.update_like_count()
    liked = created
    if request.htmx:
        return render(
            request,
            "public/partials/like_button.html",
            {"project": project, "user_has_liked": liked},
        )
    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({"liked": liked, "like_count": project.like_count})
    return redirect("public:project_detail", project_id=project.id)


@login_required
def add_public_comment(request, project_id):
    """AJAX view to add a comment to a public project"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    project = get_public_project(project_id)

    form = PublicCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.project = project
        comment.author = request.user
        comment.save()

        # Get author profile for response
        author_profile = comment.author_profile
        author_name = (
            author_profile.user.get_full_name() if author_profile else request.user.username
        )

        return JsonResponse(
            {
                "success": True,
                "comment": {
                    "id": comment.id,
                    "content": comment.content,
                    "author_name": author_name,
                    "created_at": comment.created_at.strftime("%d/%m/%Y à %H:%M"),
                },
            }
        )
    else:
        return JsonResponse({"success": False, "errors": form.errors})


@login_required
@require_POST
def add_project_comment(request, project_id):
    """Public comment on a showcased project (HTMX returns the refreshed thread)."""
    project = get_public_project(project_id)
    form = PublicCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.project = project
        comment.author = request.user
        comment.save()
        messages.success(request, "Votre commentaire a été publié.")
        form = PublicCommentForm()
    else:
        messages.error(request, " ".join(form.errors.get("content", ["Commentaire invalide."])))
    if request.htmx:
        return render(
            request,
            "public/partials/comments.html",
            {"project": project, "comments": _public_comments(project), "comment_form": form},
        )
    return redirect("public:project_detail", project_id=project.id)


@login_required
def report_project(request, project_id):
    """Report inappropriate public project"""
    project = get_public_project(project_id)

    # Check if user already reported this project
    if project.reports.filter(reporter=request.user).exists():
        messages.warning(request, "Vous avez déjà signalé ce projet.")
        return redirect("public:project_detail", project_id=project.id)

    if request.method == "POST":
        form = ProjectReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.project = project
            report.reporter = request.user
            report.save()

            # Atomic increment; auto-flag after 3 reports
            Project.objects.filter(pk=project.pk).update(report_count=F("report_count") + 1)
            Project.objects.filter(pk=project.pk, report_count__gte=3).update(is_reported=True)

            messages.success(
                request, "Merci pour votre signalement. Il sera examiné par notre équipe."
            )
            return redirect("public:project_detail", project_id=project.id)
    else:
        form = ProjectReportForm()

    context = {"project": project, "form": form}
    return render(request, "public/report_project.html", context)
