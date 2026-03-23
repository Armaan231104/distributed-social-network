from django import forms
from .models import RemoteNode


class RemoteNodeForm(forms.ModelForm):
    """
    Form for adding or editing a remote node connection.
    
    Allows node admins to specify the remote node's URL and credentials
    for HTTP Basic Authentication.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'class': 'form-input'
        }),
        help_text="Username and password from the remote node's README",
        label="Password"
    )

    class Meta:
        model = RemoteNode
        fields = ['url', 'username', 'password', 'is_active']
        widgets = {
            'url': forms.URLInput(attrs={
                'placeholder': 'https://other-node.herokuapp.com',
                'class': 'form-input'
            }),
            'username': forms.TextInput(attrs={
                'placeholder': 'Username',
                'class': 'form-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'id': 'id_is_active'
            }),
        }
        labels = {
            'url': 'Node URL',
            'username': 'Username',
            'is_active': 'Active',
        }
        help_texts = {
            'url': 'The base URL of the remote node (e.g., https://other-node.herokuapp.com)',
            'is_active': 'Allow this node to connect and receive shares',
        }

    def clean_url(self):
        url = self.cleaned_data.get('url')
        if url:
            url = url.rstrip('/')
        return url
