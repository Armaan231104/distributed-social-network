from django import forms
from .models import Author
import re
from django.contrib.auth.models import User


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
    
class SignUpForm(forms.ModelForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "placeholder": "Username",
            "class": "form-input"
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "Email",
            "class": "form-input"
        })
    )

    display_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            "placeholder": "Display Name",
            "class": "form-input"
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Password",
            "class": "form-input"
        })
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Confirm Password",
            "class": "form-input"
        })
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data