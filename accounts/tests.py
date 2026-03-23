from django.test import TestCase, Client
from django.contrib.auth.models import User
import json
from unittest.mock import patch, MagicMock

from accounts.models import Author, FollowRequest, Follow


class AuthorModelTest(TestCase):
    """Tests for the Author model methods."""
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_author_str_representation(self):
        """Verifies author string representation is the display name."""
        self.assertEqual(str(self.author1), self.author1.displayName)
    
    def test_author_is_local(self):
        """Verifies local authors are correctly identified as local."""
        self.assertTrue(self.author1.is_local)
    
    def test_author_followers_count(self):
        """Verifies get_followers_count returns correct number."""
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertEqual(self.author1.get_followers_count(), 1)
    
    def test_author_following_count(self):
        """Verifies get_following_count returns correct number."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertEqual(self.author1.get_following_count(), 1)
    
    def test_is_following(self):
        """Verifies is_following correctly identifies following relationship."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertTrue(self.author1.is_following(self.author2))
        self.assertFalse(self.author2.is_following(self.author1))
    
    def test_is_followed_by(self):
        """Verifies is_followed_by correctly identifies follower relationship."""
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertTrue(self.author1.is_followed_by(self.author2))
        self.assertFalse(self.author2.is_followed_by(self.author1))
    
    def test_is_friend(self):
        """Verifies is_friend returns true only for mutual follows."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertTrue(self.author1.is_friend(self.author2))
        Follow.objects.filter(follower=self.author2, followee=self.author1).delete()
        self.assertFalse(self.author1.is_friend(self.author2))
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertTrue(self.author1.is_friend(self.author2))
        Follow.objects.filter(follower=self.author2, followee=self.author1).delete()
        self.assertFalse(self.author1.is_friend(self.author2))


class FollowRequestModelTest(TestCase):
    """Tests for FollowRequest model creation and constraints."""
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_follow_request_creation(self):
        """Verifies new follow requests default to PENDING status."""
        fr = FollowRequest.objects.create(
            actor=self.author1,
            object=self.author2,
            summary='Author One wants to follow Author Two'
        )
        self.assertEqual(fr.status, FollowRequest.Status.PENDING)
    
    def test_follow_request_unique_constraint(self):
        """Verifies duplicate follow requests between same actors are blocked."""
        FollowRequest.objects.create(
            actor=self.author1,
            object=self.author2,
            summary='First request'
        )
        with self.assertRaises(Exception):
            FollowRequest.objects.create(
                actor=self.author1,
                object=self.author2,
                summary='Duplicate request'
            )


class FollowModelTest(TestCase):
    """Tests for Follow model creation and relationships."""
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_follow_creation(self):
        """Verifies follow object is created and accessible via following relationship."""
        follow = Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertIn(follow, self.author1.following.all())
    
    def test_follow_unique_constraint(self):
        """Verifies duplicate follows between same authors are blocked."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        with self.assertRaises(Exception):
            Follow.objects.create(follower=self.author1, followee=self.author2)
    
    def test_follow_relationships(self):
        """Verifies follow correctly sets follower and followee relationships."""
        follow = Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertEqual(follow.follower, self.author1)
        self.assertIn(follow, self.author1.following.all())
        self.assertIn(follow, self.author2.followers.all())


class AuthorAPITest(TestCase):
    """Tests for author list and detail API endpoints."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        # Login for local access
        self.client.login(username='author1', password='testpass123')
    
    def test_list_authors(self):
        """Verifies GET /api/authors/ returns authors list with correct type."""
        response = self.client.get('/api/authors/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'authors')
    
    def test_get_author_detail(self):
        """Verifies GET /api/authors/{id}/ returns author with correct type."""
        response = self.client.get(f'/api/authors/{self.author1.id.rstrip("/")}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'author')
    
    def test_get_nonexistent_author(self):
        """Verifies 404 returned for non-existent author."""
        response = self.client.get('/api/authors/99999/')
        self.assertEqual(response.status_code, 404)


class FollowingAPITest(TestCase):
    """Tests for the following list API endpoint (Story 5)."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_list_following_empty(self):
        """Verifies following list returns empty array when not following anyone."""
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        response = self.client.get(f'/api/authors/{author_fqid}/following/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'following')
    
    def test_list_following_with_follows(self):
        """Verifies following list returns correct authors when following."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        response = self.client.get(f'/api/authors/{author_fqid}/following/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['following']), 1)


class FollowersAPITest(TestCase):
    """Tests for the followers list API endpoint (Story 3)."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_list_followers_empty(self):
        """Verifies followers list returns empty array when no followers."""
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        response = self.client.get(f'/api/authors/{author_fqid}/followers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'followers')
    
    def test_list_followers_with_followers(self):
        """Verifies followers list returns correct authors when followers exist."""
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        response = self.client.get(f'/api/authors/{author_fqid}/followers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['followers']), 1)


class FriendsAPITest(TestCase):
    """Tests for the friends list API endpoint."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_list_friends_empty(self):
        """Verifies friends list returns empty array when no friends."""
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        response = self.client.get(f'/api/authors/{author_fqid}/friends/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'friends')
        self.assertEqual(data['friends'], [])
    
    def test_list_friends_with_friends(self):
        """Verifies friends list returns correct authors when mutual follows exist."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        response = self.client.get(f'/api/authors/{author_fqid}/friends/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['friends']), 1)
    
    def test_list_friends_not_mutual(self):
        """Verifies one-way follow does not create friend."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        response = self.client.get(f'/api/authors/{author_fqid}/friends/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['friends']), 0)
    
    def test_list_friends_pagination(self):
        """Verifies friends list pagination works correctly."""
        # Create 5 mutual follows (friends)
        for i in range(5):
            user = User.objects.create_user(username=f'friend{i}', password='testpass123')
            author = user.author
            Follow.objects.create(follower=self.author1, followee=author)
            Follow.objects.create(follower=author, followee=self.author1)
        
        self.client.login(username='author1', password='testpass123')
        author_fqid = self.author1.id.rstrip('/')
        
        # Page 1, size 2
        response = self.client.get(f'/api/authors/{author_fqid}/friends/?page=1&size=2')
        data = response.json()
        self.assertEqual(data['count'], 5)
        self.assertEqual(len(data['friends']), 2)
        self.assertEqual(data['page_number'], 1)
        self.assertEqual(data['size'], 2)
        
        # Page 3, size 2
        response = self.client.get(f'/api/authors/{author_fqid}/friends/?page=3&size=2')
        data = response.json()
        self.assertEqual(len(data['friends']), 1)


class FollowRequestAPITest(TestCase):
    """Tests for the follow requests list API endpoint (Story 4)."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_list_follow_requests_requires_auth(self):
        """Verifies 403 returned when not authenticated."""
        response = self.client.get(f'/api/authors/{self.author1.id.rstrip("/")}/follow_requests/')
        self.assertEqual(response.status_code, 403)
    
    def test_list_follow_requests_empty(self):
        """Verifies empty array returned when no pending requests."""
        self.client.login(username='author1', password='testpass123')
        response = self.client.get(f'/api/authors/{self.author1.id.rstrip("/")}/follow_requests/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['follow_requests'], [])
    
    def test_list_follow_requests_with_pending(self):
        """Verifies pending requests are returned correctly."""
        FollowRequest.objects.create(
            actor=self.author2,
            object=self.author1,
            summary='Author Two wants to follow Author One'
        )
        self.client.login(username='author1', password='testpass123')
        response = self.client.get(f'/api/authors/{self.author1.id.rstrip("/")}/follow_requests/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['follow_requests']), 1)


class FollowViewTest(TestCase):
    """Tests for follow/unfollow API endpoints (Stories 1, 2, 5)."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_follow_requires_auth(self):
        """Verifies 403 returned when not authenticated."""
        response = self.client.put(
            f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author2.id.rstrip("/")}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
    
    @patch('accounts.views.requests.post')
    def test_follow_local_author_creates_request(self, mock_post):
        """Verifies follow creates pending request, not follow (per spec)."""
        mock_post.return_value = MagicMock(status_code=201)
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author2.id.rstrip("/")}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            FollowRequest.objects.filter(
                actor=self.author1,
                object=self.author2,
                status=FollowRequest.Status.PENDING
            ).exists()
        )
        self.assertFalse(self.author1.is_following(self.author2))
    
    def test_unfollow_author(self):
        """Verifies unfollow removes follow relationship."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.client.login(username='author1', password='testpass123')
        response = self.client.delete(f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author2.id.rstrip("/")}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.author1.is_following(self.author2))
    
    def test_unfollow_removes_friend_status(self):
        """Verifies unfollowing a friend removes friend status."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertTrue(self.author1.is_friend(self.author2))
        self.client.login(username='author1', password='testpass123')
        self.client.delete(f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author2.id.rstrip("/")}/')
        self.assertFalse(self.author1.is_friend(self.author2))
    
    def test_cannot_follow_self(self):
        """Verifies 400 returned when trying to follow yourself."""
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author1.id.rstrip("/")}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Cannot follow yourself', response.json()['error'])
    
    def test_cannot_follow_already_following(self):
        """Verifies 400 returned when already following."""
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author2.id.rstrip("/")}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Already following', response.json()['error'])
    
    def test_resend_after_rejection(self):
        """Verifies rejected requests can be resent."""
        FollowRequest.objects.create(
            actor=self.author1,
            object=self.author2,
            summary='Rejected request',
            status=FollowRequest.Status.REJECTED
        )
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author2.id.rstrip("/")}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        req = FollowRequest.objects.get(actor=self.author1, object=self.author2)
        self.assertEqual(req.status, FollowRequest.Status.PENDING)
    
    def test_cannot_send_duplicate_request(self):
        """Verifies 400 returned when pending request already exists."""
        FollowRequest.objects.create(
            actor=self.author1,
            object=self.author2,
            summary='Pending request',
            status=FollowRequest.Status.PENDING
        )
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.author1.id.rstrip("/")}/following/{self.author2.id.rstrip("/")}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('already pending', response.json()['error'])
    
    def test_cancel_pending_request(self):
        """Verifies cancel request endpoint deletes pending requests."""
        FollowRequest.objects.create(
            actor=self.author1,
            object=self.author2,
            summary='Request to cancel',
            status=FollowRequest.Status.PENDING
        )
        self.client.login(username='author1', password='testpass123')
        response = self.client.get(f'/cancel-request/{self.author2.id}/')
        self.assertEqual(response.status_code, 302)  # Redirect
        # Request should be deleted
        self.assertFalse(
            FollowRequest.objects.filter(
                actor=self.author1,
                object=self.author2,
                status=FollowRequest.Status.PENDING
            ).exists()
        )


class AcceptRejectFollowTest(TestCase):
    """Tests for accept/reject follow request endpoints (Story 3)."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_accept_follow_request(self):
        """Verifies accepting a follow request sets status to ACCEPTED."""
        Follow.objects.create(follower=self.author2, followee=self.author1)
        follow_request = FollowRequest.objects.create(
            actor=self.author2,
            object=self.author1,
            summary='Author Two wants to follow Author One',
            status=FollowRequest.Status.PENDING
        )
        
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.author1.id.rstrip("/")}/followers/{self.author2.id.rstrip("/")}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        follow_request.refresh_from_db()
        self.assertEqual(follow_request.status, FollowRequest.Status.ACCEPTED)
    
    def test_reject_follow_request(self):
        """Verifies rejecting a follow request sets status to REJECTED."""
        FollowRequest.objects.create(
            actor=self.author2,
            object=self.author1,
            summary='Author Two wants to follow Author One',
            status=FollowRequest.Status.PENDING
        )
        
        self.client.login(username='author1', password='testpass123')
        response = self.client.delete(f'/api/authors/{self.author1.id.rstrip("/")}/followers/{self.author2.id.rstrip("/")}/')
        self.assertEqual(response.status_code, 200)
        follow_request = FollowRequest.objects.first()
        self.assertEqual(follow_request.status, FollowRequest.Status.REJECTED)


class InboxFollowRequestTest(TestCase):
    """Tests for receiving remote follow requests via inbox (Story 2)."""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        # Create a remote node for authentication
        from nodes.models import RemoteNode
        self.remote_node = RemoteNode.objects.create(
            url='http://remote-node.com',
            username='remote_user',
            password='remote_pass',
            is_active=True
        )
    
    def test_receive_remote_follow_request(self):
        """Verifies remote follow requests are created via inbox endpoint."""
        import base64
        follow_data = {
            'type': 'follow',
            'summary': 'Remote Author wants to follow Author One',
            'actor': {
                'type': 'author',
                'id': 'http://remote-node.com/api/authors/999/',
                'host': 'http://remote-node.com/api/',
                'displayName': 'Remote Author',
            },
            'object': {
                'type': 'author',
                'id': self.author1.id,
                'host': self.author1.host,
                'displayName': self.author1.displayName,
            }
        }
        
        # Authenticate with the remote node credentials
        credentials = base64.b64encode(b'remote_user:remote_pass').decode()
        
        response = self.client.post(
            f'/api/authors/{self.author1.id.rstrip("/")}/inbox/',
            data=json.dumps(follow_data),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Basic {credentials}'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            FollowRequest.objects.filter(
                actor__id='http://remote-node.com/api/authors/999/',
                object=self.author1,
                status=FollowRequest.Status.PENDING
            ).exists()
        )


class AuthorSignalTest(TestCase):
    """Tests for Django signals that auto-create Author on User creation."""
    
    def test_author_created_on_user_creation(self):
        """Verifies Author is automatically created when User is created."""
        user = User.objects.create_user(username='newauthor', password='pass123')
        self.assertTrue(Author.objects.filter(user=user).exists())
    
    def test_author_has_fqid(self):
        """Verifies Author has a fully qualified ID."""
        user = User.objects.create_user(username='newauthor2', password='pass123')
        author = Author.objects.get(user=user)
        self.assertIn('/api/authors/', author.id)
    
    def test_author_username_as_displayname(self):
        """Verifies Author displayName defaults to username."""
        user = User.objects.create_user(username='testuser', password='pass123')
        author = Author.objects.get(user=user)
        self.assertEqual(author.displayName, 'testuser')


class AuthorAdminDeleteTest(TestCase):
    """Tests for admin delete functionality - delete author and user together."""
    
    def setUp(self):
        self.client = Client()
    
    def test_delete_author_also_deletes_user(self):
        """Verifies deleting an Author also deletes the associated User."""
        user = User.objects.create_user(username='testauthor', password='pass123')
        author = Author.objects.get(user=user)
        
        author_id = author.id
        user_id = user.id
        
        author.delete()
        
        self.assertFalse(Author.objects.filter(id=author_id).exists())
        self.assertFalse(User.objects.filter(id=user_id).exists())
    
    def test_delete_author_with_follows_cleans_up(self):
        """Verifies deleting Author also cleans up Follow/FollowRequest records."""
        user1 = User.objects.create_user(username='author1', password='pass123')
        user2 = User.objects.create_user(username='author2', password='pass123')
        author1 = Author.objects.get(user=user1)
        author2 = Author.objects.get(user=user2)
        
        Follow.objects.create(follower=author1, followee=author2)
        Follow.objects.create(follower=author2, followee=author1)
        
        author1_id = author1.id
        user1_id = user1.id
        
        author1.delete()
        
        self.assertFalse(Author.objects.filter(id=author1_id).exists())
        self.assertFalse(User.objects.filter(id=user1_id).exists())
        self.assertFalse(Follow.objects.filter(follower_id=author1_id).exists())
    
    def test_delete_remote_author_without_user(self):
        """Verifies deleting a remote Author (no User) works without errors."""
        remote_author = Author.objects.create(
            id='http://remote.com/api/authors/abc/',
            host='http://remote.com/api/',
            displayName='Remote Author',
            is_approved=True,
            user=None
        )
        
        remote_author.delete()
        
        self.assertFalse(Author.objects.filter(id=remote_author.id).exists())
