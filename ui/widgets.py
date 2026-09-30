"""Native date pickers (PLAN P6.3).

<input type="date"> / type="datetime-local" only accept ISO values; with the French
locale Django would render "30/09/2026" and the browser would show an empty field.
These widgets always render ISO (parsing accepts ISO in every locale).
"""

from django import forms


class NativeDateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class NativeDateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%dT%H:%M")
