from django import forms
from .models import Project, ProjectDeliverable

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'project_type', 'module_or_company', 
                  'technologies', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }



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