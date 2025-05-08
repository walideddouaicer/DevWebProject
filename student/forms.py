from django import forms
from .models import Project, ProjectDeliverable, StudentProfile, ProjectMilestone

class ProjectForm(forms.ModelForm):
    
    
    collaborators = forms.ModelMultipleChoiceField(
        queryset=StudentProfile.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'select-multiple'}),
        help_text="Commencez à taper le nom d'un étudiant pour le trouver (maximum 10)"
    )
    
    # Rest of your form class remains the same

    class Meta:
        model = Project
        fields = ['title', 'description', 'project_type', 'module_or_company', 
                  'technologies', 'start_date', 'end_date', 'collaborators']
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