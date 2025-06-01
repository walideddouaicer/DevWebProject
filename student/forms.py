from django import forms
from .models import Project, ProjectDeliverable, StudentProfile, ProjectMilestone

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
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }
    
    def __init__(self, *args, **kwargs):
        # Get the current student to exclude from collaborator choices
        current_student = kwargs.pop('current_student', None)
        super().__init__(*args, **kwargs)
        
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