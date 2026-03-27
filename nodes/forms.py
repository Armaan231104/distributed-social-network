from django import forms
from .models import RemoteNode
from .utils import validate_remote_node_credentials


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
        help_text="Password for HTTP Basic Authentication to the remote node",
        label="Password"
    )

    class Meta:
        model = RemoteNode
        fields = ['url', 'username', 'password', 'is_active']
        widgets = {
            'url': forms.URLInput(attrs={
                'placeholder': 'https://node.herokuapp.com',
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
            if url.endswith('/api'):
                url = url[:-4]
        return url

    def clean(self):
        cleaned_data = super().clean()
        url = cleaned_data.get('url')
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if not url or not username or not password:
            return cleaned_data

        is_valid, error_message = validate_remote_node_credentials(url, username, password)
        if not is_valid:
            raise forms.ValidationError(error_message)

        return cleaned_data
