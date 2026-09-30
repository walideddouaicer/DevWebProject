from django import forms

from teacher.forms import ModuleCreationForm


class AdminModuleForm(ModuleCreationForm):
    """Module create/edit for administrators (same validation as the teacher form)."""

    class Meta(ModuleCreationForm.Meta):
        fields = ModuleCreationForm.Meta.fields + ["is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classroom"].required = False
        self.fields["is_active"].required = False
        if self.instance.pk:
            # A module code is shared with students (join by code): it never changes.
            self.fields["code"].disabled = True
            self.fields["code"].required = False

    def clean_code(self):
        if self.instance.pk:
            return self.instance.code
        return super().clean_code()


class ModerationForm(forms.Form):
    ACTIONS = [("hide", "Masquer"), ("unhide", "Rétablir"), ("dismiss", "Classer")]

    action = forms.ChoiceField(choices=ACTIONS)
    admin_notes = forms.CharField(max_length=2000, strip=True, required=False)
