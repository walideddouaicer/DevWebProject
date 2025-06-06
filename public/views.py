# public/views.py
from django.shortcuts import render
from django.db.models import Count
from student.models import Project, StudentProfile
from teacher.models import TeacherProfile  
from administrator.models import AdminProfile

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