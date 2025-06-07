from django import forms
from .models import Project, ProjectDeliverable, StudentProfile, ProjectMilestone, ProjectReport, PublicProjectComment

class ProjectForm(forms.ModelForm):
    
    collaborators = forms.ModelMultipleChoiceField(
        queryset=StudentProfile.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'select-multiple'}),
        help_text="Commencez à taper le nom d'un étudiant pour le trouver (maximum 10)"
    )
    
    # Module selection field
    module = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="Sélectionnez un module (optionnel)",
        help_text="Associez ce projet à l'un de vos modules"
    )

    class Meta:
        model = Project
        fields = ['title', 'description', 'project_type', 'module_or_company', 
                  'technologies', 'start_date', 'end_date', 'module', 'collaborators']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Entrez le titre de votre projet...'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 5,
                'placeholder': 'Décrivez votre projet en détail...'
            }),
            'project_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'module_or_company': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Module ou entreprise...'
            }),
            'technologies': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Python, Django, React, PostgreSQL...'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        # Get the current student to exclude from collaborator choices
        current_student = kwargs.pop('current_student', None)
        super().__init__(*args, **kwargs)
        
        # Add CSS classes to fields that don't have widgets defined in Meta
        self.fields['module'].widget.attrs.update({'class': 'form-select'})
        self.fields['collaborators'].widget.attrs.update({'class': 'form-select'})
        
        if current_student:
            # Exclude the current student from collaborator choices
            self.fields['collaborators'].queryset = StudentProfile.objects.exclude(id=current_student.id)
            
            # Set module queryset safely
            try:
                from teacher.models import ModuleEnrollment, Module
                
                # Get enrolled modules for this student
                enrolled_modules = ModuleEnrollment.objects.filter(
                    student=current_student,
                    is_active=True
                ).values_list('module', flat=True)
                
                # Set the queryset - handle empty case
                if enrolled_modules:
                    self.fields['module'].queryset = Module.objects.filter(
                        id__in=enrolled_modules,
                        is_active=True
                    ).order_by('code')
                else:
                    # If no enrolled modules, set empty queryset
                    self.fields['module'].queryset = Module.objects.none()
                    
            except Exception as e:
                # Fallback to empty queryset if there's any import or query issue
                from teacher.models import Module
                self.fields['module'].queryset = Module.objects.none()
        else:
            # If no current student, set empty queryset
            from teacher.models import Module
            self.fields['module'].queryset = Module.objects.none()

    def clean_collaborators(self):
        collaborators = self.cleaned_data.get('collaborators')
        if collaborators and len(collaborators) > 10:
            raise forms.ValidationError("Vous ne pouvez sélectionner que 10 collaborateurs maximum.")
        return collaborators



class DeliverableForm(forms.ModelForm):
    class Meta:
        model = ProjectDeliverable
        fields = ['file', 'file_type', 'name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nom du livrable'}),
        }
    

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Limit file size to 10MB
            if file.size > 10 * 1024 * 1024:  # 10MB in bytes
                raise forms.ValidationError("Le fichier est trop volumineux. La taille maximale est de 10 Mo.")
        return file
    


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = ProjectMilestone
        fields = ['title', 'description', 'due_date', 'completed']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


# Updated forms.py - Much simpler approach

class MakeProjectPublicForm(forms.ModelForm):
    """Simple form to make project public with optional enhancements"""
    
    showcase_tags = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Sélectionnez jusqu'à 5 tags (optionnel)"
    )
    
    class Meta:
        model = Project
        fields = ['public_cover_image', 'public_description', 'public_demo_url', 
                  'public_github_url', 'public_portfolio_url']
        widgets = {
            'public_cover_image': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
            'public_description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Description publique personnalisée (optionnel - sinon votre description principale sera utilisée)...'
            }),
            'public_demo_url': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://demo.monprojet.com (optionnel)'
            }),
            'public_github_url': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://github.com/username/projet (optionnel)'
            }),
            'public_portfolio_url': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://portfolio.com/projet (optionnel)'
            }),
        }
        labels = {
            'public_cover_image': 'Image de couverture (optionnel)',
            'public_description': 'Description publique (optionnel)',
            'public_demo_url': 'Lien de démonstration (optionnel)',
            'public_github_url': 'Lien GitHub (optionnel)',
            'public_portfolio_url': 'Lien portfolio (optionnel)',
        }
        help_texts = {
            'public_cover_image': 'Image qui représentera votre projet. Si non fournie, une image par défaut sera utilisée.',
            'public_description': 'Si vide, votre description principale sera utilisée.',
            'public_demo_url': 'Lien vers une démonstration en ligne',
            'public_github_url': 'Lien vers le code source',
            'public_portfolio_url': 'Lien vers votre portfolio',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import ShowcaseTag
        self.fields['showcase_tags'].queryset = ShowcaseTag.objects.all()
    
    def clean_public_cover_image(self):
        image = self.cleaned_data.get('public_cover_image')
        if image and image.size > 5 * 1024 * 1024:  # 5MB limit
            raise forms.ValidationError("L'image est trop volumineuse (max 5MB).")
        return image


class QuickPublishForm(forms.Form):
    """Ultra-simple form for instant publishing with current content"""
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        label="Je confirme vouloir rendre ce projet visible publiquement"
    )


class ProjectReportForm(forms.ModelForm):
    """Form for reporting inappropriate public projects"""
    
    class Meta:
        model = ProjectReport
        fields = ['reason', 'description']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Décrivez le problème en détail...'
            })
        }
        labels = {
            'reason': 'Raison du signalement',
            'description': 'Description détaillée'
        }


class PublicCommentForm(forms.ModelForm):
    """Simple comment form"""
    class Meta:
        model = PublicProjectComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Votre commentaire...',
                'maxlength': 1000
            })
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content and len(content.strip()) < 5:
            raise forms.ValidationError("Le commentaire doit contenir au moins 5 caractères.")
        return content