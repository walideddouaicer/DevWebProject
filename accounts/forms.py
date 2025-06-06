# accounts/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import PendingRegistration
from student.models import StudentProfile
from teacher.models import TeacherProfile

class BaseSignupForm(forms.ModelForm):
    """Base form for all user types"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8,
        help_text="Au moins 8 caractères"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirmer le mot de passe"
    )
    
    class Meta:
        model = PendingRegistration
        fields = ['first_name', 'last_name', 'username', 'email', 'password']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return password_confirm
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ce nom d'utilisateur existe déjà.")
        if PendingRegistration.objects.filter(username=username).exists():
            raise forms.ValidationError("Une demande d'inscription avec ce nom d'utilisateur est en attente.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Un compte avec cette adresse email existe déjà.")
        if PendingRegistration.objects.filter(email=email).exists():
            raise forms.ValidationError("Une demande d'inscription avec cette adresse email est en attente.")
        return email


class StudentSignupForm(BaseSignupForm):
    """Signup form for students"""
    student_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Votre numéro d'étudiant ENSA"
    )
    year_of_study = forms.ChoiceField(
        choices=[(3, '3ème année'), (4, '4ème année'), (5, '5ème année')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    department = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Votre filière (ex: Génie Informatique)"
    )
    
    class Meta(BaseSignupForm.Meta):
        fields = BaseSignupForm.Meta.fields + ['student_id', 'year_of_study', 'department']
    
    def save(self, commit=True):
        registration = super().save(commit=False)
        registration.role = 'student'
        registration.password = make_password(self.cleaned_data['password'])
        if commit:
            registration.save()
        return registration


class TeacherSignupForm(BaseSignupForm):
    """Signup form for teachers"""
    teacher_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Votre identifiant enseignant",
        required=False
    )
    department = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Votre département"
    )
    
    class Meta(BaseSignupForm.Meta):
        fields = BaseSignupForm.Meta.fields + ['teacher_id', 'department']
    
    def save(self, commit=True):
        registration = super().save(commit=False)
        registration.role = 'teacher'
        registration.password = make_password(self.cleaned_data['password'])
        if commit:
            registration.save()
        return registration