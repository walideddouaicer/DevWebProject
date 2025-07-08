from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    Module, ProjectAssignment, ProjectOption, 
    ModuleAssignment, TeacherProfile
)
from student.models import StudentProfile

class ModuleCreationForm(forms.ModelForm):
    """Form for teachers to create new modules"""
    
    class Meta:
        model = Module
        fields = [
            'name', 'code', 'description', 'academic_year', 
            'semester', 'classroom'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nom du module (ex: Programmation Orientée Objet)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Code du module (ex: CS301)',
                'style': 'text-transform: uppercase;'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Description détaillée du module...'
            }),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '2024-2025'
            }),
            'semester': forms.Select(attrs={
                'class': 'form-select'
            }),
            'classroom': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Salle de classe (ex: A201, Lab Informatique)'
            }),
        }
        labels = {
            'name': 'Nom du module',
            'code': 'Code du module',
            'description': 'Description',
            'academic_year': 'Année académique',
            'semester': 'Semestre',
            'classroom': 'Salle de classe',
        }
        help_texts = {
            'code': 'Code unique pour identifier le module (sera automatiquement en majuscules)',
            'academic_year': 'Format: YYYY-YYYY (exemple: 2024-2025)',
            'classroom': 'Salle ou laboratoire où se déroulent les cours (optionnel)',
        }
    
    def clean_code(self):
        """Validate and format module code"""
        code = self.cleaned_data.get('code', '').upper().strip()
        
        if not code:
            raise ValidationError("Le code du module est obligatoire.")
        
        if len(code) < 3 or len(code) > 10:
            raise ValidationError("Le code du module doit contenir entre 3 et 10 caractères.")
        
        # Check if code already exists
        if Module.objects.filter(code=code).exists():
            raise ValidationError(f"Un module avec le code '{code}' existe déjà.")
        
        return code
    
    def clean_academic_year(self):
        """Validate academic year format"""
        year = self.cleaned_data.get('academic_year', '').strip()
        
        if not year:
            raise ValidationError("L'année académique est obligatoire.")
        
        # Check format YYYY-YYYY
        if '-' not in year or len(year) != 9:
            raise ValidationError("Format attendu: YYYY-YYYY (exemple: 2024-2025)")
        
        try:
            start_year, end_year = year.split('-')
            start_year = int(start_year)
            end_year = int(end_year)
            
            if end_year != start_year + 1:
                raise ValidationError("L'année de fin doit être celle qui suit l'année de début.")
                
        except ValueError:
            raise ValidationError("Format d'année invalide. Utilisez YYYY-YYYY.")
        
        return year


class ProjectAssignmentForm(forms.ModelForm):
    """Form for creating project assignments - UPDATED TO USE TEAM TERMINOLOGY"""
    
    class Meta:
        model = ProjectAssignment
        fields = [
            'title', 'description', 'instructions', 'assignment_type',
            'deadline', 'is_team_work', 'min_team_size', 'max_team_size',
            'target_selection', 'selection_deadline'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Titre du devoir (ex: Développement d\'une application web)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Description générale du devoir...'
            }),
            'instructions': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 6,
                'placeholder': 'Instructions détaillées pour les étudiants...'
            }),
            'assignment_type': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'toggleAssignmentOptions(this.value)'
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local'
            }),
            'is_team_work': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'onchange': 'toggleTeamOptions(this.checked)'
            }),
            'min_team_size': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '1',
                'max': '10'
            }),
            'max_team_size': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '1',
                'max': '10'
            }),
            'target_selection': forms.Select(attrs={
                'class': 'form-select'
            }),
            'selection_deadline': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local'
            }),
        }
        labels = {
            'title': 'Titre du devoir',
            'description': 'Description',
            'instructions': 'Instructions détaillées',
            'assignment_type': 'Type d\'assignation',
            'deadline': 'Date limite de rendu',
            'is_team_work': 'Travail en équipe',
            'min_team_size': 'Taille minimale de l\'équipe',
            'max_team_size': 'Taille maximale de l\'équipe',
            'target_selection': 'Sélection des étudiants',
            'selection_deadline': 'Date limite de sélection des projets',
        }
        help_texts = {
            'assignment_type': 'Assignation directe: vous assignez le projet. Choix multiple: les étudiants choisissent parmi vos options.',
            'deadline': 'Date et heure limite pour soumettre le projet',
            'is_team_work': 'Cochez si le devoir doit être fait en équipe',
            'selection_deadline': 'Date limite pour choisir un projet (choix multiple uniquement)',
        }
    
    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        # Set intelligent default values
        if not self.instance.pk:
            now = timezone.now()
            # Default deadline to 2 weeks from now
            self.fields['deadline'].initial = now + timezone.timedelta(weeks=2)
            # Default selection deadline to 1 week from now
            self.fields['selection_deadline'].initial = now + timezone.timedelta(weeks=1)
    
    def clean_title(self):
        """Validate assignment title"""
        title = self.cleaned_data.get('title', '').strip()
        
        if not title:
            raise ValidationError("Le titre du devoir est obligatoire.")
        
        if len(title) < 5:
            raise ValidationError("Le titre doit contenir au moins 5 caractères.")
        
        return title
    
    def clean_deadline(self):
        """Validate main deadline"""
        deadline = self.cleaned_data.get('deadline')
        
        if not deadline:
            raise ValidationError("La date limite est obligatoire.")
        
        now = timezone.now()
        
        # Must be at least 1 hour in the future
        if deadline <= now + timezone.timedelta(hours=1):
            raise ValidationError("La date limite doit être au moins 1 heure dans le futur.")
        
        # Should not be more than 6 months in the future
        if deadline > now + timezone.timedelta(days=180):
            raise ValidationError("La date limite ne peut pas être plus de 6 mois dans le futur.")
        
        return deadline
    
    def clean_selection_deadline(self):
        """Validate project selection deadline"""
        deadline = self.cleaned_data.get('selection_deadline')
        assignment_type = self.cleaned_data.get('assignment_type')
        
        if assignment_type == 'choice_based' and not deadline:
            raise ValidationError("Une date limite de sélection est requise pour les devoirs à choix multiple.")
        
        if deadline:
            now = timezone.now()
            
            if deadline <= now:
                raise ValidationError("La date limite de sélection doit être dans le futur.")
        
        return deadline
    
    def clean_min_team_size(self):
        """Validate minimum team size"""
        min_size = self.cleaned_data.get('min_team_size')
        is_team_work = self.cleaned_data.get('is_team_work', False)
        
        if is_team_work:
            if not min_size or min_size < 2:
                raise ValidationError("Pour un travail en équipe, la taille minimale doit être d'au moins 2.")
            
            if min_size > 10:
                raise ValidationError("La taille minimale ne peut pas dépasser 10.")
        
        return min_size
    
    def clean_max_team_size(self):
        """Validate maximum team size"""
        max_size = self.cleaned_data.get('max_team_size')
        is_team_work = self.cleaned_data.get('is_team_work', False)
        
        if is_team_work:
            if not max_size or max_size < 2:
                raise ValidationError("Pour un travail en équipe, la taille maximale doit être d'au moins 2.")
            
            if max_size > 15:
                raise ValidationError("La taille maximale ne peut pas dépasser 15.")
        
        return max_size
    
    def clean(self):
        """Cross-field validation for team assignments"""
        cleaned_data = super().clean()
        
        assignment_type = cleaned_data.get('assignment_type')
        is_team_work = cleaned_data.get('is_team_work', False)
        min_team_size = cleaned_data.get('min_team_size')
        max_team_size = cleaned_data.get('max_team_size')
        deadline = cleaned_data.get('deadline')
        selection_deadline = cleaned_data.get('selection_deadline')
        
        errors = {}
        now = timezone.now()
        
        # 1. Validate team sizes
        if is_team_work:
            if not min_team_size or min_team_size < 2:
                errors['min_team_size'] = "La taille minimale doit être d'au moins 2 pour un travail en équipe."
            if not max_team_size or max_team_size < 2:
                errors['max_team_size'] = "La taille maximale doit être d'au moins 2 pour un travail en équipe."
            if min_team_size and max_team_size and min_team_size > max_team_size:
                errors['max_team_size'] = "La taille maximale ne peut pas être inférieure à la minimale."
        
        # 2. Validate deadlines chronological order
        deadlines = []
        if selection_deadline:
            deadlines.append(('selection', selection_deadline))
        if deadline:
            deadlines.append(('final', deadline))
        
        # Sort deadlines and check order
        deadlines.sort(key=lambda x: x[1])
        
        # All deadlines must be in future
        for name, dt in deadlines:
            if dt <= now:
                field_name = {
                    'selection': 'selection_deadline',
                    'final': 'deadline'
                }[name]
                errors[field_name] = "Cette date doit être dans le futur."
        
        # Check minimum gaps between deadlines (24 hours)
        for i in range(len(deadlines) - 1):
            current = deadlines[i][1]
            next_deadline = deadlines[i + 1][1]
            if (next_deadline - current).total_seconds() < 24 * 3600:
                errors['deadline'] = "Il doit y avoir au moins 24 heures entre chaque échéance."
                break
        
        # 3. Type-specific validation
        if assignment_type == 'choice_based' and not selection_deadline:
            errors['selection_deadline'] = "Une date limite de sélection est requise pour les devoirs à choix multiple."
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class ProjectOptionForm(forms.ModelForm):
    """Form for creating project options in choice-based assignments - ENHANCED"""
    
    class Meta:
        model = ProjectOption
        fields = [
            'title', 'description', 'requirements', 'estimated_difficulty',
            'is_unique', 'max_teams'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Titre du projet (ex: Système de gestion de bibliothèque)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Description détaillée du projet...'
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Compétences requises, technologies à utiliser...'
            }),
            'estimated_difficulty': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_unique': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'onchange': 'toggleMaxTeams(this.checked)'
            }),
            'max_teams': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '1',
                'max': '20'
            }),
        }
        labels = {
            'title': 'Titre du projet',
            'description': 'Description',
            'requirements': 'Exigences et compétences',
            'estimated_difficulty': 'Difficulté estimée',
            'is_unique': 'Projet unique',
            'max_teams': 'Nombre maximum d\'équipes',
        }
        help_texts = {
            'is_unique': 'Si coché, un seul équipe peut choisir ce projet',
            'max_teams': 'Nombre maximum d\'équipes pouvant choisir ce projet (si non unique)',
        }
    
    def clean_title(self):
        """Validate project title"""
        title = self.cleaned_data.get('title', '').strip()
        
        if not title:
            raise ValidationError("Le titre du projet est obligatoire.")
        
        if len(title) < 5:
            raise ValidationError("Le titre doit contenir au moins 5 caractères.")
        
        return title
    
    def clean_description(self):
        """Validate project description"""
        description = self.cleaned_data.get('description', '').strip()
        
        if not description:
            raise ValidationError("La description du projet est obligatoire.")
        
        if len(description) < 20:
            raise ValidationError("La description doit contenir au moins 20 caractères.")
        
        return description
    
    def clean_max_teams(self):
        """Validate maximum teams"""
        max_teams = self.cleaned_data.get('max_teams')
        is_unique = self.cleaned_data.get('is_unique', True)
        
        if not is_unique:
            if not max_teams or max_teams < 1:
                raise ValidationError("Pour un projet non unique, vous devez spécifier un nombre maximum d'équipes d'au moins 1.")
            
            if max_teams > 50:
                raise ValidationError("Le nombre maximum d'équipes ne peut pas dépasser 50.")
        
        return max_teams
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        is_unique = cleaned_data.get('is_unique', True)
        max_teams = cleaned_data.get('max_teams')
        
        # For unique projects, max_teams should be 1
        if is_unique:
            cleaned_data['max_teams'] = 1
        elif not max_teams or max_teams < 1:
            raise ValidationError({
                'max_teams': "Pour un projet non unique, vous devez spécifier un nombre maximum d'équipes."
            })
        
        return cleaned_data


class StudentSelectionForm(forms.Form):
    """Form for selecting specific students for direct assignments - ENHANCED"""
    
    selected_students = forms.ModelMultipleChoiceField(
        queryset=StudentProfile.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'student-checkbox'
        }),
        required=False,
        label="Sélectionner les étudiants"
    )
    
    select_all = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'onchange': 'toggleSelectAll(this.checked)'
        }),
        label="Sélectionner tous les étudiants"
    )
    
    def __init__(self, *args, **kwargs):
        module = kwargs.pop('module', None)
        super().__init__(*args, **kwargs)
        
        if module:
            # Get enrolled students in this module
            enrolled_students = StudentProfile.objects.filter(
                module_enrollments__module=module,
                module_enrollments__is_active=True
            ).select_related('user').order_by('user__first_name', 'user__last_name')
            
            self.fields['selected_students'].queryset = enrolled_students
            
            # Add count information
            student_count = enrolled_students.count()
            self.fields['selected_students'].help_text = f"Total de {student_count} étudiants inscrits à ce module"
    
    def clean_selected_students(self):
        """Validate student selection"""
        selected_students = self.cleaned_data.get('selected_students', [])
        select_all = self.cleaned_data.get('select_all', False)
        
        if not select_all and not selected_students:
            raise ValidationError("Vous devez sélectionner au moins un étudiant ou cocher 'Sélectionner tous les étudiants'.")
        
        return selected_students


# Additional forms for filtering and progress tracking

class AssignmentProgressForm(forms.Form):
    """Form for teachers to track assignment progress"""
    
    status_filter = forms.ChoiceField(
        choices=[
            ('', 'Tous les statuts'),
            ('assigned', 'Assigné'),
            ('started', 'Commencé'),
            ('submitted', 'Soumis'),
            ('validated', 'Validé'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search_query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Rechercher par nom d\'étudiant ou équipe...'
        })
    )


class AssignmentFilterForm(forms.Form):
    """Form for filtering assignments in teacher dashboard - ENHANCED"""
    
    status = forms.ChoiceField(
        choices=[
            ('', 'Tous les statuts'),
            ('draft', 'Brouillon'),
            ('published', 'Publié'),
            ('in_progress', 'En cours'),
            ('completed', 'Terminé'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    assignment_type = forms.ChoiceField(
        choices=[
            ('', 'Tous les types'),
            ('direct', 'Assignation directe'),
            ('choice_based', 'Choix multiple'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    module = forms.ModelChoiceField(
        queryset=Module.objects.none(),
        required=False,
        empty_label="Tous les modules",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Rechercher par titre...'
        })
    )
    
    deadline_filter = forms.ChoiceField(
        choices=[
            ('', 'Toutes les échéances'),
            ('upcoming', 'Échéances prochaines (7 jours)'),
            ('overdue', 'En retard'),
            ('today', 'Aujourd\'hui'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        if teacher:
            # Get modules assigned to this teacher
            self.fields['module'].queryset = Module.objects.filter(
                assignments__teacher=teacher,
                assignments__is_active=True,
                is_active=True
            ).distinct().order_by('code')