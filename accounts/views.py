from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import StudentSignupForm, TeacherSignupForm
from .utils import send_registration_confirmation_email


def signup_choice(request):
    """Let users choose their role before signup."""
    return render(request, "accounts/signup_choice.html")


def _signup(request, form_class, role, role_display):
    """Create a PendingRegistration; an administrator activates the account later."""
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        registration = form.save()
        message = "Demande d'inscription envoyée. Un administrateur va l'examiner."
        if send_registration_confirmation_email(registration):
            message += f" Un e-mail de confirmation a été envoyé à {registration.email}."
        messages.success(request, message)
        return redirect("public:homepage")
    context = {"form": form, "role": role, "role_display": role_display}
    return render(request, "accounts/signup_form.html", context)


def student_signup(request):
    return _signup(request, StudentSignupForm, "student", "Étudiant")


def teacher_signup(request):
    return _signup(request, TeacherSignupForm, "teacher", "Enseignant")
