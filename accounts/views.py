# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import StudentSignupForm, TeacherSignupForm
from .models import PendingRegistration
from .utils import send_registration_confirmation_email

def signup_choice(request):
    """Let users choose their role before signup"""
    return render(request, 'accounts/signup_choice.html')

def student_signup(request):
    """Student registration form"""
    if request.method == 'POST':
        form = StudentSignupForm(request.POST)
        if form.is_valid():
            registration = form.save()
            
            # Send confirmation email
            email_sent = send_registration_confirmation_email(registration)
            
            if email_sent:
                messages.success(
                    request, 
                    "Votre demande d'inscription a été soumise! "
                    "Un administrateur l'examinera sous peu. "
                    "Vous avez reçu un email de confirmation."
                )
            else:
                messages.success(
                    request, 
                    "Votre demande d'inscription a été soumise! "
                    "Un administrateur l'examinera sous peu. "
                    "(Note: L'email de confirmation n'a pas pu être envoyé)"
                )
            
            return redirect('public:homepage')
    else:
        form = StudentSignupForm()
    
    context = {
        'form': form,
        'role': 'student',
        'role_display': 'Étudiant'
    }
    return render(request, 'accounts/signup_form.html', context)

def teacher_signup(request):
    """Teacher registration form"""
    if request.method == 'POST':
        form = TeacherSignupForm(request.POST)
        if form.is_valid():
            registration = form.save()
            
            # Send confirmation email
            email_sent = send_registration_confirmation_email(registration)
            
            if email_sent:
                messages.success(
                    request,
                    "Votre demande d'inscription a été soumise! "
                    "Un administrateur l'examinera sous peu. "
                    "Vous avez reçu un email de confirmation."
                )
            else:
                messages.success(
                    request,
                    "Votre demande d'inscription a été soumise! "
                    "Un administrateur l'examinera sous peu. "
                    "(Note: L'email de confirmation n'a pas pu être envoyé)"
                )
            
            return redirect('public:homepage')
    else:
        form = TeacherSignupForm()
    
    context = {
        'form': form,
        'role': 'teacher',
        'role_display': 'Enseignant'
    }
    return render(request, 'accounts/signup_form.html', context)

def admin_signup(request):
    """Administrator registration - requires existing admin approval"""
    if not request.user.is_authenticated:
        messages.error(request, "Vous devez être connecté pour créer un compte administrateur.")
        return redirect('login')
    
    # Check if current user is admin
    from administrator.models import AdminProfile
    try:
        AdminProfile.objects.get(user=request.user)
    except AdminProfile.DoesNotExist:
        messages.error(request, "Seuls les administrateurs peuvent créer des comptes administrateur.")
        return redirect('public:homepage')
    
    # Admin creation logic here...
    messages.info(request, "Création d'administrateur - Fonctionnalité en développement.")
    return redirect('administrator:dashboard')