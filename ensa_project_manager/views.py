# ensa_project_manager/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from administrator.models import AdminProfile
from student.models import StudentProfile
from teacher.models import TeacherProfile


@login_required
def smart_redirect(request):
    """Smart view that redirects users to the appropriate dashboard"""
    user = request.user

    # Check if user has an administrator profile first (highest priority)
    try:
        AdminProfile.objects.get(user=user)
        return redirect("administrator:dashboard")
    except AdminProfile.DoesNotExist:
        pass

    # Check if user has a teacher profile
    try:
        TeacherProfile.objects.get(user=user)
        return redirect("teacher:dashboard")
    except TeacherProfile.DoesNotExist:
        pass

    # Check if user has a student profile
    try:
        StudentProfile.objects.get(user=user)
        return redirect("student:dashboard")
    except StudentProfile.DoesNotExist:
        pass

    # If no profile exists, redirect to student dashboard as fallback
    return redirect("student:dashboard")


def security_txt(request):
    """RFC 9116 security contact (/.well-known/security.txt)."""
    from datetime import timedelta

    from django.conf import settings
    from django.shortcuts import render
    from django.utils import timezone

    contact = settings.SECURITY_CONTACT
    expires = (timezone.now() + timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")
    return render(
        request,
        "security.txt",
        {"contact": contact, "expires": expires},
        content_type="text/plain; charset=utf-8",
    )


def favicon(request):
    """Browsers ask for /favicon.ico; point them to the (hashed) static SVG."""
    from django.http import HttpResponsePermanentRedirect
    from django.templatetags.static import static

    return HttpResponsePermanentRedirect(static("icons/favicon.svg"))
