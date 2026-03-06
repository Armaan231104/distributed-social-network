from django import forms
from .models import Author
import re


class AuthorUpdateForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['displayName', 'description', 'github', 'profileImage', 'web']

    def clean_github(self):
        github = self.cleaned_data.get("github")

        if github:
            pattern = r"^https:\/\/(www\.)?github\.com\/[A-Za-z0-9_-]+\/?$"
            if not re.match(pattern, github):
                raise forms.ValidationError(
                    "Enter a valid GitHub profile URL (https://github.com/username)"
                )

        return github