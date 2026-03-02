import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Follow
from posts.models import Entry

class PostsApiTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", password="pass12345")
        self.user2 = User.objects.create_user(username="u2", password="pass12345")
        self.admin = User.objects.create_user(
            username="admin", password="pass12345", is_staff=True
        )

    def login(self, username):
        ok = self.client.login(username=username, password="pass12345")
        self.assertTrue(ok)

    def test_create_entry_json_can_set_visibility(self):
        self.login("u1")

        resp = self.client.post(
            "/posts/api/entries/create/",
            data=json.dumps(
                {
                    "title": "Unlisted Post",
                    "content": "Link only",
                    "contentType": "text/plain",
                    "visibility": "UNLISTED",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)

        entry = Entry.objects.get(id=resp.json()["id"])
        self.assertEqual(entry.visibility, "UNLISTED")

    def test_my_entries_excludes_deleted(self):
        self.login("u1")

        e1 = Entry.objects.create(
            author=self.user1, title="A", content="x", content_type="text/plain"
        )
        e2 = Entry.objects.create(
            author=self.user1, title="B", content="y", content_type="text/plain"
        )
        e2.soft_delete()

        resp = self.client.get("/posts/api/entries/mine/")
        self.assertEqual(resp.status_code, 200)

        ids = {item["id"] for item in resp.json()}
        self.assertIn(str(e1.id), ids)
        self.assertNotIn(str(e2.id), ids)

    def test_get_public_entry_anonymous_ok(self):
        e = Entry.objects.create(
            author=self.user1,
            title="Pub",
            content="x",
            content_type="text/plain",
            visibility="PUBLIC",
        )

        resp = self.client.get(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_get_unlisted_entry_anonymous_ok(self):
        e = Entry.objects.create(
            author=self.user1,
            title="Unlisted",
            content="x",
            content_type="text/plain",
            visibility="UNLISTED",
        )

        resp = self.client.get(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_get_deleted_entry_hidden_from_non_admin_including_author(self):
        e = Entry.objects.create(
            author=self.user1,
            title="Del",
            content="x",
            content_type="text/plain",
            visibility="PUBLIC",
        )
        e.soft_delete()

        resp = self.client.get(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp.status_code, 404)

        self.login("u1")
        resp2 = self.client.get(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp2.status_code, 404)

        self.login("u2")
        resp3 = self.client.get(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp3.status_code, 404)

    def test_get_deleted_entry_visible_to_node_admin_staff(self):
        e = Entry.objects.create(
            author=self.user1,
            title="Del",
            content="x",
            content_type="text/plain",
            visibility="PUBLIC",
        )
        e.soft_delete()

        self.login("admin")
        resp = self.client.get(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_edit_entry_only_author(self):
        e = Entry.objects.create(
            author=self.user1, title="T", content="x", content_type="text/plain"
        )

        self.login("u2")
        resp = self.client.put(
            f"/posts/api/entries/{e.id}/edit/",
            data=json.dumps({"title": "Hacked"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

        self.login("u1")
        resp2 = self.client.put(
            f"/posts/api/entries/{e.id}/edit/",
            data=json.dumps({"title": "Updated"}),
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 200)

        e.refresh_from_db()
        self.assertEqual(e.title, "Updated")

    def test_delete_entry_only_author_and_soft_delete(self):
        e = Entry.objects.create(
            author=self.user1, title="T", content="x", content_type="text/plain"
        )

        self.login("u2")
        resp = self.client.delete(f"/posts/api/entries/{e.id}/delete/")
        self.assertEqual(resp.status_code, 403)

        self.login("u1")
        resp2 = self.client.delete(f"/posts/api/entries/{e.id}/delete/")
        self.assertEqual(resp2.status_code, 200)

        e.refresh_from_db()
        self.assertEqual(e.visibility, "DELETED")

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
        
    '''
    Tests: author can create a plaintext post
    '''
    def test_create_entry_plaintext_json_success(self):
        self.login("u1")

        resp = self.post_json({
            "title": "Plain",
            "content": "hello world",
            "contentType": "text/plain",
            "visibility": "PUBLIC",
        })
        self.assertEqual(resp.status_code, 201)

        entry = Entry.objects.get(id=resp.json()["id"])
        self.assertEqual(entry.author, self.user1)
        self.assertEqual(entry.title, "Plain")
        self.assertEqual(entry.content, "hello world")
        self.assertEqual(entry.content_type, "text/plain")
        self.assertEqual(entry.visibility, "PUBLIC")
    
    '''
    Tests: author can create a commonmark post
    '''
    def test_create_entry_commonmark_json_success(self):
        self.login("u1")

        md = "- item one\n- item two\n\n[Example](https://example.com)"
        resp = self.post_json({
            "title": "MD",
            "content": md,
            "contentType": "text/markdown",
            "visibility": "PUBLIC",
        })
        self.assertEqual(resp.status_code, 201)

        entry = Entry.objects.get(id=resp.json()["id"])
        self.assertEqual(entry.content_type, "text/markdown")
        self.assertIn("item one", entry.content)
        self.assertIn("https://example.com", entry.content)

    '''
    Tests: author can create an image post
    '''
    def test_create_entry_image_multipart_success(self):
        self.login("u1")

        resp = self.post_image_multipart(title="Pic", content="caption here")
        self.assertEqual(resp.status_code, 201)

        entry = Entry.objects.get(id=resp.json()["id"])
        self.assertEqual(entry.author, self.user1)
        self.assertEqual(entry.title, "Pic")
        self.assertEqual(entry.content, "caption here")
        self.assertEqual(entry.content_type, "image")

        # Only run this assertion if your model actually has an image field
        self.assertTrue(hasattr(entry, "image"))
        self.assertTrue(entry.image.name)  # saved file path

    '''
    Tests: author cannot upload an invalid file type
    '''
    def test_create_entry_rejects_invalid_content_type(self):
        self.login("u1")

        resp = self.post_json({
            "title": "Bad",
            "content": "nope",
            "contentType": "video/mp4",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())
    
    '''
    Tests: author cannot save an image post if they have not uploaded an image
    '''
    def test_create_entry_image_missing_file_rejected(self):
        self.login("u1")

        resp = self.client.post(
            "/posts/api/entries/create/",
            data={
                "title": "No image",
                "content": "caption",
                "contentType": "image",
                "visibility": "PUBLIC",
                # missing "image"
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    '''
    Tests: author must be logged in to create entries
    '''
    def test_create_entry_requires_login(self):
        resp = self.post_json({
            "title": "NoAuth",
            "content": "test",
            "contentType": "text/plain",
        })
        # login_required usually redirects to login page (302)
        self.assertIn(resp.status_code, [302, 401, 403])

    def test_create_entry_rejects_get(self):
        self.login("u1")
        resp = self.client.get("/posts/api/entries/create/")
        self.assertEqual(resp.status_code, 400)

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