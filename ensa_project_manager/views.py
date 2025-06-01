# ensa_project_manager/views.py
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from student.models import StudentProfile
from teacher.models import TeacherProfile
from administrator.models import AdminProfile

@login_required
def smart_redirect(request):
    """Smart view that redirects users to the appropriate dashboard"""
    user = request.user
    
    # Check if user has an administrator profile first (highest priority)
    try:
        AdminProfile.objects.get(user=user)
        return redirect('administrator:dashboard')
    except AdminProfile.DoesNotExist:
        pass
    
    # Check if user has a teacher profile
    try:
        TeacherProfile.objects.get(user=user)
        return redirect('teacher:dashboard')
    except TeacherProfile.DoesNotExist:
        pass
    
    # Check if user has a student profile
    try:
        StudentProfile.objects.get(user=user)
        return redirect('student:dashboard')
    except StudentProfile.DoesNotExist:
        pass
    
    # If no profile exists, redirect to student dashboard as fallback
    return redirect('student:dashboard')