from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from student.models import StudentProfile
from teacher.models import TeacherProfile

@login_required
def smart_redirect(request):
    """Simple view that redirects users to the appropriate dashboard"""
    user = request.user
    
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