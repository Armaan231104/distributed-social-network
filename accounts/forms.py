from django import forms
from .models import Author

class AuthorUpdateForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['displayName', 'description', 'github', 'profileImage', 'web']