from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, Mock
import base64
import requests
from .models import RemoteNode


class RemoteNodeModelTest(TestCase):
    """Tests for the RemoteNode model."""

    def test_create_node(self):
        """Test creating a remote node."""
        node = RemoteNode.objects.create(
            url='https://other-node.herokuapp.com',
            username='admin',
            password='secret123',
            is_active=True
        )
        self.assertEqual(node.url, 'https://other-node.herokuapp.com')
        self.assertEqual(node.username, 'admin')
        self.assertTrue(node.is_active)
        self.assertIsNotNone(node.created_at)

    def test_get_host(self):
        """Test getting the host URL without trailing slash."""
        node = RemoteNode.objects.create(
            url='https://other-node.herokuapp.com/',
            username='admin',
            password='secret123'
        )
        self.assertEqual(node.get_host(), 'https://other-node.herokuapp.com')

    def test_disable_enable(self):
        """Test disabling and enabling a node."""
        node = RemoteNode.objects.create(
            url='https://other-node.herokuapp.com',
            username='admin',
            password='secret123',
            is_active=True
        )
        
        node.disable()
        self.assertFalse(node.is_active)
        
        node.enable()
        self.assertTrue(node.is_active)

    def test_unique_url(self):
        """Test that URL must be unique."""
        RemoteNode.objects.create(
            url='https://other-node.herokuapp.com',
            username='admin',
            password='secret123'
        )
        with self.assertRaises(Exception):
            RemoteNode.objects.create(
                url='https://other-node.herokuapp.com',
                username='other',
                password='other123'
            )


class NodeUITest(TestCase):
    """Tests for the node management UI."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='adminpass',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='user',
            password='userpass'
        )
        self.client = Client()

    def test_nodes_list_requires_staff(self):
        """Test that non-staff users cannot access nodes list."""
        self.client.login(username='user', password='userpass')
        response = self.client.get(reverse('nodes-list'))
        self.assertEqual(response.status_code, 302)

    def test_nodes_list_accessible_to_staff(self):
        """Test that staff users can access nodes list."""
        self.client.login(username='admin', password='adminpass')
        response = self.client.get(reverse('nodes-list'))
        self.assertEqual(response.status_code, 200)

    def test_add_node(self):
        """Test adding a new node."""
        self.client.login(username='admin', password='adminpass')
        with patch('nodes.forms.validate_remote_node_credentials', return_value=(True, None)):
            response = self.client.post(reverse('add-node'), {
                'url': 'https://new-node.herokuapp.com',
                'username': 'nodeadmin',
                'password': 'nodepass123',
                'is_active': True
            }, follow=True)
        
        self.assertTrue(RemoteNode.objects.filter(
            url='https://new-node.herokuapp.com'
        ).exists())

    def test_add_node_shows_error_when_connection_validation_fails(self):
        """Invalid node credentials should not create a node and should show an error."""
        self.client.login(username='admin', password='adminpass')

        with patch(
            'nodes.forms.validate_remote_node_credentials',
            return_value=(False, 'Connection failed. Check that the username and password are correct.')
        ):
            response = self.client.post(reverse('add-node'), {
                'url': 'https://bad-node.herokuapp.com',
                'username': 'wrong',
                'password': 'wrongpass',
                'is_active': True
            })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RemoteNode.objects.filter(url='https://bad-node.herokuapp.com').exists())
        self.assertContains(response, 'Connection failed. Check that the username and password are correct.')

    def test_edit_node(self):
        """Test editing an existing node."""
        node = RemoteNode.objects.create(
            url='https://old-node.herokuapp.com',
            username='olduser',
            password='oldpass'
        )
        
        self.client.login(username='admin', password='adminpass')
        with patch('nodes.forms.validate_remote_node_credentials', return_value=(True, None)):
            response = self.client.post(reverse('edit-node', args=[node.id]), {
                'url': 'https://old-node.herokuapp.com',
                'username': 'newuser',
                'password': 'newpass',
                'is_active': False
            }, follow=True)
        
        node.refresh_from_db()
        self.assertEqual(node.username, 'newuser')
        self.assertFalse(node.is_active)

    def test_delete_node(self):
        """Test deleting a node."""
        node = RemoteNode.objects.create(
            url='https://delete-node.herokuapp.com',
            username='admin',
            password='secret123'
        )
        
        self.client.login(username='admin', password='adminpass')
        response = self.client.post(reverse('delete-node', args=[node.id]), follow=True)
        
        self.assertFalse(RemoteNode.objects.filter(id=node.id).exists())

    def test_toggle_node(self):
        """Test toggling node active status."""
        node = RemoteNode.objects.create(
            url='https://toggle-node.herokuapp.com',
            username='admin',
            password='secret123',
            is_active=True
        )
        
        self.client.login(username='admin', password='adminpass')
        self.client.post(reverse('toggle-node', args=[node.id]))
        
        node.refresh_from_db()
        self.assertFalse(node.is_active)
        
        self.client.post(reverse('toggle-node', args=[node.id]))
        node.refresh_from_db()
        self.assertTrue(node.is_active)


class NodeAPITest(TestCase):
    """Tests for the node API endpoints."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='adminpass',
            is_staff=True
        )
        self.client = Client()

    def test_list_nodes_api_requires_auth(self):
        """Test that API requires authentication."""
        response = self.client.get(reverse('node-list-api'))
        self.assertEqual(response.status_code, 403)

    def test_list_nodes_api(self):
        """Test listing nodes via API."""
        self.client.login(username='admin', password='adminpass')
        RemoteNode.objects.create(
            url='https://api-node.herokuapp.com',
            username='admin',
            password='secret123'
        )
        
        response = self.client.get(reverse('node-list-api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['type'], 'nodes')
        self.assertEqual(len(response.json()['nodes']), 1)

    def test_create_node_api(self):
        """Test creating a node via API."""
        self.client.login(username='admin', password='adminpass')
        with patch('nodes.forms.validate_remote_node_credentials', return_value=(True, None)):
            response = self.client.post(reverse('node-list-api'), {
                'url': 'https://api-create.herokuapp.com',
                'username': 'admin',
                'password': 'secret123'
            })
        
        self.assertEqual(response.status_code, 201)
        self.assertTrue(RemoteNode.objects.filter(
            url='https://api-create.herokuapp.com'
        ).exists())

    def test_update_node_api(self):
        """Test updating a node via API."""
        node = RemoteNode.objects.create(
            url='https://api-update.herokuapp.com',
            username='admin',
            password='secret123',
            is_active=True
        )
        
        self.client.login(username='admin', password='adminpass')
        with patch('nodes.forms.validate_remote_node_credentials', return_value=(True, None)):
            response = self.client.patch(
                reverse('node-detail-api', args=[node.id]),
                {'is_active': False},
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 200)
        node.refresh_from_db()
        self.assertFalse(node.is_active)

    def test_update_node_api_rejects_invalid_connection(self):
        """PATCH should not save invalid remote node credentials."""
        node = RemoteNode.objects.create(
            url='https://api-update.herokuapp.com',
            username='admin',
            password='secret123',
            is_active=True
        )

        self.client.login(username='admin', password='adminpass')
        with patch(
            'nodes.forms.validate_remote_node_credentials',
            return_value=(False, 'Connection failed. The remote node could not be reached at that URL.')
        ):
            response = self.client.patch(
                reverse('node-detail-api', args=[node.id]),
                {'url': 'https://missing-node.herokuapp.com'},
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 400)
        node.refresh_from_db()
        self.assertEqual(node.url, 'https://api-update.herokuapp.com')
        self.assertIn('Connection failed. The remote node could not be reached at that URL.', str(response.json()))


class RemoteNodeValidationTest(TestCase):
    """Tests for remote node connection validation helpers."""

    @patch('nodes.utils.requests.get')
    def test_validate_remote_node_credentials_accepts_successful_auth(self, mock_get):
        response = Mock(status_code=200)
        mock_get.return_value = response

        from nodes.utils import validate_remote_node_credentials

        is_valid, error_message = validate_remote_node_credentials(
            'https://remote-node.example.com',
            'nodeuser',
            'nodepass'
        )

        self.assertTrue(is_valid)
        self.assertIsNone(error_message)
        mock_get.assert_called_once_with(
            'https://remote-node.example.com/api/authors/',
            auth=('nodeuser', 'nodepass'),
            timeout=5,
            headers={'Accept': 'application/json'},
        )

    @patch('nodes.utils.requests.get')
    def test_validate_remote_node_credentials_rejects_auth_errors(self, mock_get):
        response = Mock(status_code=401)
        mock_get.return_value = response

        from nodes.utils import validate_remote_node_credentials

        is_valid, error_message = validate_remote_node_credentials(
            'https://remote-node.example.com',
            'wrong',
            'wrongpass'
        )

        self.assertFalse(is_valid)
        self.assertEqual(
            error_message,
            'Connection failed. Check that the username and password are correct.'
        )

    @patch('nodes.utils.requests.get')
    def test_validate_remote_node_credentials_rejects_unreachable_url(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError

        from nodes.utils import validate_remote_node_credentials

        is_valid, error_message = validate_remote_node_credentials(
            'https://missing-node.example.com',
            'nodeuser',
            'nodepass'
        )

        self.assertFalse(is_valid)
        self.assertEqual(
            error_message,
            'Connection failed. The remote node could not be reached at that URL.'
        )

    def test_delete_node_api(self):
        """Test deleting a node via API."""
        node = RemoteNode.objects.create(
            url='https://api-delete.herokuapp.com',
            username='admin',
            password='secret123'
        )
        
        User.objects.create_superuser(username='admin', password='adminpass', email='admin@example.com')
        self.client.login(username='admin', password='adminpass')
        response = self.client.delete(reverse('node-detail-api', args=[node.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RemoteNode.objects.filter(id=node.id).exists())


class NodeAuthenticationTest(TestCase):
    """Tests for node-to-node Basic Auth authentication."""

    def setUp(self):
        self.node = RemoteNode.objects.create(
            url='https://remote-node.herokuapp.com',
            username='nodeuser',
            password='nodepass',
            is_active=True
        )
        self.client = Client()

    def test_authenticate_valid_credentials(self):
        """Test authenticating with valid node credentials."""
        from nodes.authentication import authenticate_remote_node
        
        credentials = base64.b64encode(b'nodeuser:nodepass').decode()
        result = authenticate_remote_node(f'Basic {credentials}')
        
        self.assertIsNotNone(result)
        user, auth_info = result
        self.assertTrue(user.is_remote_node)
        self.assertEqual(auth_info['type'], 'remote_node')

    def test_authenticate_invalid_credentials(self):
        """Test authenticating with invalid credentials."""
        from nodes.authentication import authenticate_remote_node
        
        credentials = base64.b64encode(b'invalid:wrong').decode()
        result = authenticate_remote_node(f'Basic {credentials}')
        
        self.assertIsNone(result)

    def test_authenticate_inactive_node(self):
        """Test that inactive nodes cannot authenticate."""
        self.node.is_active = False
        self.node.save()
        
        from nodes.authentication import authenticate_remote_node
        
        credentials = base64.b64encode(b'nodeuser:nodepass').decode()
        result = authenticate_remote_node(f'Basic {credentials}')
        
        self.assertIsNone(result)

    def test_authenticate_no_header(self):
        """Test that missing auth header returns None."""
        from nodes.authentication import authenticate_remote_node
        
        result = authenticate_remote_node(None)
        self.assertIsNone(result)
        
        result = authenticate_remote_node('')
        self.assertIsNone(result)

    def test_authenticate_local_node(self):
        """Test authenticating with local node credentials."""
        from django.conf import settings
        from nodes.authentication import authenticate_remote_node
        
        original_username = getattr(settings, 'NODE_USERNAME', 'admin')
        original_password = getattr(settings, 'NODE_PASSWORD', 'password')
        
        settings.NODE_USERNAME = 'testadmin'
        settings.NODE_PASSWORD = 'testpass'
        
        try:
            credentials = base64.b64encode(b'testadmin:testpass').decode()
            result = authenticate_remote_node(f'Basic {credentials}')
            
            self.assertIsNotNone(result)
            user, auth_info = result
            self.assertTrue(user.is_local)
        finally:
            settings.NODE_USERNAME = original_username
            settings.NODE_PASSWORD = original_password
