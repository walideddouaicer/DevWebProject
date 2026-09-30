from django.contrib import messages
from django.shortcuts import redirect

from ..models import AdminProfile


def admin_required(view_func):
    """Decorator to ensure user is an administrator"""

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        try:
            AdminProfile.objects.get(user=request.user)
        except AdminProfile.DoesNotExist:
            messages.error(request, "Vous n'avez pas les droits d'administrateur.")
            return redirect("login")

        return view_func(request, *args, **kwargs)

    return wrapper
