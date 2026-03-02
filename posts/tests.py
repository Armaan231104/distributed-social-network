from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import Follow
from posts.models import Entry


class PostVisibilityOnProfileTest(TestCase):
    """
    Tests that post visibility rules are correctly enforced on author profile pages

    Rules used:
      PUBLIC   - visible to everyone (logged in or not)
      UNLISTED - visible only to followers and the author
      FRIENDS  - visible only to friends (they both follow each other) and the author
      DELETED  - never visible even to the author
    """

    def setUp(self):
        self.client = Client()

        # author who creates posts
        self.author_user = User.objects.create_user(
            username='author', password='testpass123'
        )
        self.author = self.author_user.author

        # user who does not follow the author
        self.non_follower_user = User.objects.create_user(
            username='non_follower', password='testpass123'
        )

        # user who follows the author but the author does not follow them back
        self.follower_user = User.objects.create_user(
            username='follower', password='testpass123'
        )
        self.follower_author = self.follower_user.author
        Follow.objects.create(follower=self.follower_author, followee=self.author)

        # user who is friends with the author
        self.friend_user = User.objects.create_user(
            username='friend', password='testpass123'
        )
        self.friend_author = self.friend_user.author
        Follow.objects.create(follower=self.friend_author, followee=self.author)
        Follow.objects.create(follower=self.author, followee=self.friend_author)

        # post creation for each visibility option
        self.public_post = Entry.objects.create(
            author=self.author_user,
            title='Public Post',
            content='Public content',
            visibility='PUBLIC',
        )
        self.unlisted_post = Entry.objects.create(
            author=self.author_user,
            title='Unlisted Post',
            content='Unlisted content',
            visibility='UNLISTED',
        )
        self.friends_post = Entry.objects.create(
            author=self.author_user,
            title='Friends Post',
            content='Friends content',
            visibility='FRIENDS',
        )
        self.deleted_post = Entry.objects.create(
            author=self.author_user,
            title='Deleted Post',
            content='Deleted content',
            visibility='DELETED',
        )

        self.profile_url = reverse(
            'author-profile', kwargs={'author_id': self.author.id}
        )
    # ------------------------------------------------------------------------------------------
    # PUBLIC POST TESTS
    # ------------------------------------------------------------------------------------------
    '''
    Tests: PUBLIC post is visible to anyone, even while not logged-in
    Pass Condition: The public post is in the profile page context
    '''
    def test_public_post_visible_to_unauthenticated_user(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.public_post, response.context['posts'])

    '''
    Tests: PUBLIC post is visible to a logged-in user who does not foolow the author
    Pass Condition: The public post is in the profile page context
    '''
    def test_public_post_visible_to_non_follower(self):
        #
        self.client.login(username='non_follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    '''
    Tests: PUBLIC post is visible to user who follows the user
    Pass Condition: The public post is in the profile page context
    '''
    def test_public_post_visible_to_follower(self):
        self.client.login(username='follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    '''
    Tests: PUBLIC post is visible to a friend
    Pass Condition: The public post is in the profile page context
    '''
    def test_public_post_visible_to_friend(self):
        self.client.login(username='friend', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    '''
    Tests: author can see their own PUBLIC post on their own profile
    Pass Condition: The public post is in the profile page context
    '''
    def test_public_post_visible_to_author_on_own_profile(self):
        self.client.login(username='author', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    # ------------------------------------------------------------------------------------------
    # UNLISTED Post Tests
    # ------------------------------------------------------------------------------------------
    '''
    Tests: UNLISTED post is hidden from users who are not logged-in
    Pass Condition: The UNLISTED post is not in the profile page context
    '''
    def test_unlisted_post_not_visible_to_unauthenticated_user(self):
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.unlisted_post, response.context['posts'])

    '''
    Tests: UNLISTED post is hidden from logged-in user that is not following the author
    Pass Condition: The UNLISTED post is not in the profile page context
    '''
    def test_unlisted_post_not_visible_to_non_follower(self):
        self.client.login(username='non_follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.unlisted_post, response.context['posts'])

    '''
    Tests: UNLISTED post is visible to logged-in user that follows the author
    Pass Condition: The UNLISTED post is in the profile page context
    '''
    def test_unlisted_post_visible_to_follower(self):
        self.client.login(username='follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.unlisted_post, response.context['posts'])

    '''
    Tests: An author can see their UNLISTED post on their own profile
    Pass Condition: The UNLISTED post is in the profile page context
    '''
    def test_unlisted_post_visible_to_friend(self):
        self.client.login(username='friend', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.unlisted_post, response.context['posts'])

    '''
    Tests: UNLISTED post is visible to the author on their own profile
    Pass Condition: Unlisted post is in the profile page context
    '''
    def test_unlisted_post_visible_to_author_on_own_profile(self):
        self.client.login(username='author', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.unlisted_post, response.context['posts'])

    # ------------------------------------------------------------------------------------------
    # FRIENDS POST TESTS
    # ------------------------------------------------------------------------------------------
    '''
    Tests: FRIENDS post is hidden from users who are not logged-in
    Pass Condition: The FRIENDS post is not in the profile page context
    '''
    def test_friends_post_not_visible_to_unauthenticated_user(self):
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.friends_post, response.context['posts'])

    '''
    Tests: FRIENDS post is hidden from loggged-in user who does not follow the author
    Pass Condition: The FRIENDS post is not in the profile page context
    '''
    def test_friends_post_not_visible_to_non_follower(self):
        self.client.login(username='non_follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.friends_post, response.context['posts'])

    '''
    Tests: FRIENDS post is hidden from logged-in user who follows the author but is not a friend
    Pass Condition: The FRIENDS post is not in the profile page context
    '''
    def test_friends_post_not_visible_to_one_way_follower(self):
        """A follower who the author does not follow back is not a friend."""
        self.client.login(username='follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.friends_post, response.context['posts'])

    '''
    Tests: FRIENDS post is visible to logged-in user who is friends with the author
    Pass Condition: The FRIENDS post is in the profile page context
    '''
    def test_friends_post_visible_to_mutual_follower(self):
        """A user who mutually follows the author (friend) can see FRIENDS posts."""
        self.client.login(username='friend', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.friends_post, response.context['posts'])

    '''
    TESTS: FRIENDS post is visible to the author on their own profile
    Pass Condition: The FRIENDS post is in the profile page context 
    '''
    def test_friends_post_visible_to_author_on_own_profile(self):
        self.client.login(username='author', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.friends_post, response.context['posts'])

    # --- DELETED post ---

    def test_deleted_post_not_visible_to_author_on_own_profile(self):
        self.client.login(username='author', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.deleted_post, response.context['posts'])

    def test_deleted_post_not_visible_to_non_follower(self):
        self.client.login(username='non_follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.deleted_post, response.context['posts'])

    def test_deleted_post_not_visible_to_follower(self):
        self.client.login(username='follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.deleted_post, response.context['posts'])

    def test_deleted_post_not_visible_to_friend(self):
        self.client.login(username='friend', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.deleted_post, response.context['posts'])
