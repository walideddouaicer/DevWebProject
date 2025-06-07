# public/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.models import User

# Import models
from student.models import (
    Project, StudentProfile, ProjectView, ProjectLike, 
    PublicProjectComment, ProjectReport, ShowcaseTag, ProjectActivity
)
from teacher.models import TeacherProfile  
from administrator.models import AdminProfile

# Import forms
from student.forms import PublicCommentForm, ProjectReportForm


def get_common_context():
    """Get common context data for all public pages"""
    return {
        'total_projects': Project.objects.count(),
        'total_students': StudentProfile.objects.count(),
        'total_teachers': TeacherProfile.objects.count(),
        'featured_projects': Project.objects.filter(
            status='validated'
        ).order_by('-created_at')[:3],  # Show 3 recent validated projects
    }


def homepage(request):
    """Landing page with app presentation and auth links"""
    context = get_common_context()
    return render(request, 'public/homepage.html', context)


def features(request):
    """Features and capabilities page"""
    context = get_common_context()
    return render(request, 'public/features.html', context)


def about(request):
    """About ENSA Project Manager page"""
    context = get_common_context()
    return render(request, 'public/about.html', context)


def explore_projects(request):
    """Public project gallery (future social feature)"""
    # For now, show validated projects
    projects = Project.objects.filter(
        status='validated'
    ).select_related('student__user', 'module').order_by('-created_at')[:12]
    
    context = get_common_context()
    context['projects'] = projects
    
    return render(request, 'public/explore_projects.html', context)


def public_projects_showcase(request):
    """Main showcase page - accessible from homepage 'Projects' button"""
    
    # Get all public projects (no admin approval needed!)
    projects = Project.objects.filter(
        is_public=True,
        is_hidden_by_admin=False  # Only hide if admin took action due to reports
    ).select_related(
        'student__user', 'module'
    ).prefetch_related(
        'showcase_tags__tag', 'deliverables'  # Include deliverables!
    )
    
    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        projects = projects.filter(
            Q(title__icontains=search_query) |
            Q(public_description__icontains=search_query) |
            Q(description__icontains=search_query) |  # Fallback to main description
            Q(technologies__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query)
        )
    
    # Filter by tag
    tag_filter = request.GET.get('tag', '')
    if tag_filter:
        projects = projects.filter(showcase_tags__tag__name=tag_filter)
    
    # Filter by project type
    type_filter = request.GET.get('type', '')
    if type_filter:
        projects = projects.filter(project_type=type_filter)
    
    # Enhanced filtering
    has_demo = request.GET.get('has_demo', '')
    if has_demo:
        projects = projects.exclude(public_demo_url='')
    
    has_github = request.GET.get('has_github', '')
    if has_github:
        projects = projects.exclude(public_github_url='')
    
    # Sorting options
    sort_by = request.GET.get('sort', 'recent')
    if sort_by == 'popular':
        projects = projects.order_by('-like_count', '-view_count')
    elif sort_by == 'views':
        projects = projects.order_by('-view_count')
    elif sort_by == 'likes':
        projects = projects.order_by('-like_count')
    elif sort_by == 'title':
        projects = projects.order_by('title')
    else:  # recent
        projects = projects.order_by('-made_public_at')
    
    # Pagination
    paginator = Paginator(projects, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    available_tags = ShowcaseTag.objects.annotate(
        project_count=Count('projectshowcasetag')
    ).filter(project_count__gt=0).order_by('name')
    
    # Statistics
    total_projects = projects.count()
    projects_with_demo = projects.exclude(public_demo_url='').count()
    projects_with_github = projects.exclude(public_github_url='').count()
    
    context = {
        'page_obj': page_obj,
        'available_tags': available_tags,
        'project_types': Project.PROJECT_TYPES,
        'search_query': search_query,
        'tag_filter': tag_filter,
        'type_filter': type_filter,
        'sort_by': sort_by,
        'has_demo': has_demo,
        'has_github': has_github,
        'total_projects': total_projects,
        'projects_with_demo': projects_with_demo,
        'projects_with_github': projects_with_github,
    }
    
    return render(request, 'public/projects_showcase.html', context)


def public_project_detail(request, project_id):
    """Detailed view of a public project - includes deliverables!"""
    
    project = get_object_or_404(
        Project.objects.select_related('student__user', 'module'),
        id=project_id,
        is_public=True,
        is_hidden_by_admin=False
    )
    
    # Track view (only once per session per project)
    view_key = f'viewed_project_{project_id}'
    if not request.session.get(view_key):
        ProjectView.objects.create(
            project=project,
            user=request.user if request.user.is_authenticated else None,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Update view count
        project.view_count += 1
        project.save(update_fields=['view_count'])
        
        # Mark as viewed in session
        request.session[view_key] = True
    
    # Get deliverables (this is what the user wanted!)
    deliverables = project.deliverables.all().order_by('-upload_date')
    
    # Get public comments
    comments = project.public_comments.filter(
        is_flagged=False
    ).select_related('author').order_by('-created_at')[:20]
    
    # Get milestones for additional context
    milestones = project.milestones.all().order_by('due_date')
    
    # Get collaborators
    collaborators = project.collaborators.all().select_related('user')
    
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
    related_projects = Project.objects.filter(
        Q(project_type=project.project_type) | Q(student=project.student),
        is_public=True,
        is_hidden_by_admin=False
    ).exclude(id=project.id).order_by('-like_count')[:4]
    
    # Comment form for authenticated users
    comment_form = None
    if request.user.is_authenticated:
        comment_form = PublicCommentForm()
    
    context = {
        'project': project,
        'deliverables': deliverables,  # Include deliverables in public view!
        'milestones': milestones,
        'collaborators': collaborators,
        'comments': comments,
        'related_projects': related_projects,
        'user_has_liked': user_has_liked,
        'can_report': can_report,
        'has_already_reported': has_already_reported, 
        'comment_form': comment_form,
    }
    
    return render(request, 'public/project_detail.html', context)


@login_required
def toggle_project_like(request, project_id):
    """AJAX view to toggle like on a public project"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    project = get_object_or_404(Project, id=project_id, is_public=True)
    
    like, created = ProjectLike.objects.get_or_create(
        project=project,
        user=request.user
    )
    
    if not created:
        # Unlike
        like.delete()
        liked = False
    else:
        # Like
        liked = True
    
    # Update project like count
    project.update_like_count()
    
    return JsonResponse({
        'liked': liked,
        'like_count': project.like_count
    })


@login_required
def add_public_comment(request, project_id):
    """AJAX view to add a comment to a public project"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    project = get_object_or_404(Project, id=project_id, is_public=True)
    
    form = PublicCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.project = project
        comment.author = request.user
        comment.save()
        
        # Get author profile for response
        author_profile = comment.author_profile
        author_name = author_profile.user.get_full_name() if author_profile else request.user.username
        
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'author_name': author_name,
                'created_at': comment.created_at.strftime('%d/%m/%Y à %H:%M'),
            }
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        })

@login_required
def add_project_comment(request, project_id):
    """Regular form submission for adding comments (not AJAX)"""
    if request.method != 'POST':
        return redirect('public:project_detail', project_id=project_id)
    
    project = get_object_or_404(Project, id=project_id, is_public=True)
    
    form = PublicCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.project = project
        comment.author = request.user
        comment.save()
        
        messages.success(request, "Votre commentaire a été ajouté avec succès!")
    else:
        messages.error(request, "Erreur dans votre commentaire. Veuillez vérifier le contenu.")
    
    return redirect('public:project_detail', project_id=project_id)




@login_required
def report_project(request, project_id):
    """Report inappropriate public project"""
    project = get_object_or_404(Project, id=project_id, is_public=True)
    
    # Check if user already reported this project
    if project.reports.filter(reporter=request.user).exists():
        messages.warning(request, "Vous avez déjà signalé ce projet.")
        return redirect('public:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        form = ProjectReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.project = project
            report.reporter = request.user
            report.save()
            
            # Update project report count
            project.report_count += 1
            if project.report_count >= 3:  # Auto-flag after 3 reports
                project.is_reported = True
            project.save(update_fields=['report_count', 'is_reported'])
            
            messages.success(request, "Merci pour votre signalement. Il sera examiné par notre équipe.")
            return redirect('public:project_detail', project_id=project.id)
    else:
        form = ProjectReportForm()
    
    context = {'project': project, 'form': form}
    return render(request, 'public/report_project.html', context)