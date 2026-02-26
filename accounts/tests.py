from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json
from unittest.mock import patch, MagicMock

from accounts.models import Author, FollowRequest, Follow


class AuthorModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_author_str_representation(self):
        self.assertEqual(str(self.author1), self.author1.displayName)
    
    def test_author_is_local(self):
        self.assertTrue(self.author1.is_local)
    
    def test_author_followers_count(self):
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertEqual(self.author1.get_followers_count(), 1)
    
    def test_author_following_count(self):
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertEqual(self.author1.get_following_count(), 1)
    
    def test_is_following(self):
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertTrue(self.author1.is_following(self.author2))
        self.assertFalse(self.author2.is_following(self.author1))
    
    def test_is_followed_by(self):
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertTrue(self.author1.is_followed_by(self.author2))
        self.assertFalse(self.author2.is_followed_by(self.author1))
    
    def test_is_friend(self):
        Follow.objects.create(follower=self.author1, followee=self.author2)
        Follow.objects.create(follower=self.author2, followee=self.author1)
        self.assertTrue(self.author1.is_friend(self.author2))
        Follow.objects.filter(follower=self.author2, followee=self.author1).delete()
        self.assertFalse(self.author1.is_friend(self.author2))


class FollowRequestModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_follow_request_creation(self):
        fr = FollowRequest.objects.create(
            actor=self.author1,
            object=self.author2,
            summary='Author One wants to follow Author Two'
        )
        self.assertEqual(fr.status, FollowRequest.Status.PENDING)
    
    def test_follow_request_unique_constraint(self):
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
    def setUp(self):
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_follow_creation(self):
        follow = Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertIn(follow, self.author1.following.all())
    
    def test_follow_unique_constraint(self):
        Follow.objects.create(follower=self.author1, followee=self.author2)
        with self.assertRaises(Exception):
            Follow.objects.create(follower=self.author1, followee=self.author2)
    
    def test_follow_relationships(self):
        follow = Follow.objects.create(follower=self.author1, followee=self.author2)
        self.assertEqual(follow.follower, self.author1)
        self.assertIn(follow, self.author1.following.all())
        self.assertIn(follow, self.author2.followers.all())


class AuthorAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
    
    def test_list_authors(self):
        response = self.client.get('/api/authors/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'authors')
    
    def test_get_author_detail(self):
        response = self.client.get(f'/api/authors/{self.user1.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'author')
    
    def test_get_nonexistent_author(self):
        response = self.client.get('/api/authors/99999/')
        self.assertEqual(response.status_code, 404)


class FollowingAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_list_following_empty(self):
        response = self.client.get(f'/api/authors/{self.user1.id}/following/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'following')
    
    def test_list_following_with_follows(self):
        Follow.objects.create(follower=self.author1, followee=self.author2)
        response = self.client.get(f'/api/authors/{self.user1.id}/following/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['items']), 1)


class FollowersAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_list_followers_empty(self):
        response = self.client.get(f'/api/authors/{self.user1.id}/followers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'followers')
    
    def test_list_followers_with_followers(self):
        Follow.objects.create(follower=self.author2, followee=self.author1)
        response = self.client.get(f'/api/authors/{self.user1.id}/followers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['items']), 1)


class FollowRequestAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_list_follow_requests_requires_auth(self):
        response = self.client.get(f'/api/authors/{self.user1.id}/follow_requests/')
        self.assertEqual(response.status_code, 403)
    
    def test_list_follow_requests_empty(self):
        self.client.login(username='author1', password='testpass123')
        response = self.client.get(f'/api/authors/{self.user1.id}/follow_requests/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['items'], [])
    
    def test_list_follow_requests_with_pending(self):
        FollowRequest.objects.create(
            actor=self.author2,
            object=self.author1,
            summary='Author Two wants to follow Author One'
        )
        self.client.login(username='author1', password='testpass123')
        response = self.client.get(f'/api/authors/{self.user1.id}/follow_requests/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['items']), 1)


class FollowViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_follow_requires_auth(self):
        response = self.client.put(
            f'/api/authors/{self.user1.id}/following/{self.user2.id}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
    
    @patch('accounts.views.requests.post')
    def test_follow_local_author_creates_request(self, mock_post):
        mock_post.return_value = MagicMock(status_code=201)
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.user1.id}/following/{self.user2.id}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        # Per spec - follow request is created, but Follow only after approval
        self.assertTrue(
            FollowRequest.objects.filter(
                actor=self.author1,
                object=self.author2,
                status=FollowRequest.Status.PENDING
            ).exists()
        )
        # Not following yet - only after approval
        self.assertFalse(self.author1.is_following(self.author2))
    
    def test_unfollow_author(self):
        Follow.objects.create(follower=self.author1, followee=self.author2)
        self.client.login(username='author1', password='testpass123')
        response = self.client.delete(f'/api/authors/{self.user1.id}/following/{self.user2.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.author1.is_following(self.author2))


class AcceptRejectFollowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
        
        self.user2 = User.objects.create_user(username='author2', password='testpass123')
        self.author2 = self.user2.author
    
    def test_accept_follow_request(self):
        Follow.objects.create(follower=self.author2, followee=self.author1)
        follow_request = FollowRequest.objects.create(
            actor=self.author2,
            object=self.author1,
            summary='Author Two wants to follow Author One',
            status=FollowRequest.Status.PENDING
        )
        
        self.client.login(username='author1', password='testpass123')
        response = self.client.put(
            f'/api/authors/{self.user1.id}/followers/{self.user2.id}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        follow_request.refresh_from_db()
        self.assertEqual(follow_request.status, FollowRequest.Status.ACCEPTED)
    
    def test_reject_follow_request(self):
        FollowRequest.objects.create(
            actor=self.author2,
            object=self.author1,
            summary='Author Two wants to follow Author One',
            status=FollowRequest.Status.PENDING
        )
        
        self.client.login(username='author1', password='testpass123')
        response = self.client.delete(f'/api/authors/{self.user1.id}/followers/{self.user2.id}/')
        self.assertEqual(response.status_code, 200)
        follow_request = FollowRequest.objects.first()
        self.assertEqual(follow_request.status, FollowRequest.Status.REJECTED)


class InboxFollowRequestTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='author1', password='testpass123')
        self.author1 = self.user1.author
    
    def test_receive_remote_follow_request(self):
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
        
        response = self.client.post(
            f'/api/authors/{self.user1.id}/inbox/',
            data=json.dumps(follow_data),
            content_type='application/json'
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
    def test_author_created_on_user_creation(self):
        user = User.objects.create_user(username='newauthor', password='pass123')
        self.assertTrue(Author.objects.filter(user=user).exists())
    
    def test_author_has_fqid(self):
        user = User.objects.create_user(username='newauthor2', password='pass123')
        author = Author.objects.get(user=user)
        self.assertIn('/api/authors/', author.id)
    
    def test_author_username_as_displayname(self):
        user = User.objects.create_user(username='testuser', password='pass123')
        author = Author.objects.get(user=user)
        self.assertEqual(author.displayName, 'testuser')
