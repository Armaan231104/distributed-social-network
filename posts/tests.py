import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Author, Follow
from posts.models import Entry
from nodes.models import RemoteNode


class PostsApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username="u1", password="pass12345")
        self.user2 = User.objects.create_user(username="u2", password="pass12345")
        self.admin = User.objects.create_user(
            username="admin", password="pass12345", is_staff=True
        )

    def post_json(self, payload):
        return self.client.post(
            "/posts/api/entries/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def post_image_multipart(self, title="Img", content="caption", visibility="PUBLIC"):
        image_file = SimpleUploadedFile(
            "test.png",
            b"\x89PNG\r\n\x1a\nfakepngdata",
            content_type="image/png",
        )
        return self.client.post(
            "/posts/api/entries/",
            data={
                "title": title,
                "content": content,
                "contentType": "image",
                "visibility": visibility,
                "image": image_file,
            },
        )

    def login(self, username):
        ok = self.client.login(username=username, password="pass12345")
        self.assertTrue(ok)

    def test_create_entry_json_can_set_visibility(self):
        self.login("u1")

        resp = self.client.post(
            "/posts/api/entries/",
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
        resp = self.client.patch(
            f"/posts/api/entries/{e.id}/",
            data=json.dumps({"title": "Hacked"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

        self.login("u1")
        resp2 = self.client.patch(
            f"/posts/api/entries/{e.id}/",
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
        resp = self.client.delete(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp.status_code, 403)

        self.login("u1")
        resp2 = self.client.delete(f"/posts/api/entries/{e.id}/")
        self.assertEqual(resp2.status_code, 200)

        e.refresh_from_db()
        self.assertEqual(e.visibility, "DELETED")

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

    '''
    Tests: author can create an image post
    '''
    def test_create_entry_image_multipart_success(self):
        self.login("u1")

        resp = self.post_image_multipart(title="Pic", content="caption here")
        self.assertEqual(resp.status_code, 201)

        entry = Entry.objects.get(id=resp.json()["id"])
        self.assertEqual(entry.author, self.user1)

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

    '''
    Tests: author cannot save an image post if they have not uploaded an image
    '''
    def test_create_entry_image_missing_file_rejected(self):
        self.login("u1")

        resp = self.client.post(
            "/posts/api/entries/",
            data={
                "title": "No image",
                "content": "caption",
                "contentType": "image",
                "visibility": "PUBLIC",
            },
        )
        self.assertEqual(resp.status_code, 400)

    '''
    Tests: author must be logged in to create entries
    '''
    def test_create_entry_requires_login(self):
        resp = self.post_json({
            "title": "NoAuth",
            "content": "test",
            "contentType": "text/plain",
        })
        self.assertIn(resp.status_code, [302, 401, 403])

    def test_create_entry_rejects_get(self):
        self.login("u1")
        resp = self.client.get("/posts/api/entries/")
        self.assertEqual(resp.status_code, 400)


class PostVisibilityOnProfileTest(TestCase):
    """
    Tests that post visibility rules are correctly enforced on author profile pages
    """

    def setUp(self):
        self.client = Client()

        self.author_user = User.objects.create_user(
            username='author', password='testpass123'
        )
        self.author = self.author_user.author

        self.non_follower_user = User.objects.create_user(
            username='non_follower', password='testpass123'
        )

        self.follower_user = User.objects.create_user(
            username='follower', password='testpass123'
        )
        self.follower_author = self.follower_user.author
        Follow.objects.create(follower=self.follower_author, followee=self.author)

        self.friend_user = User.objects.create_user(
            username='friend', password='testpass123'
        )
        self.friend_author = self.friend_user.author
        Follow.objects.create(follower=self.friend_author, followee=self.author)
        Follow.objects.create(follower=self.author, followee=self.friend_author)

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

    # --- PUBLIC ---

    def test_public_post_visible_to_unauthenticated_user(self):
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    def test_public_post_visible_to_non_follower(self):
        self.client.login(username='non_follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    def test_public_post_visible_to_follower(self):
        self.client.login(username='follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    def test_public_post_visible_to_friend(self):
        self.client.login(username='friend', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    def test_public_post_visible_to_author_on_own_profile(self):
        self.client.login(username='author', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.public_post, response.context['posts'])

    # --- UNLISTED ---

    def test_unlisted_post_not_visible_to_unauthenticated_user(self):
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.unlisted_post, response.context['posts'])

    def test_unlisted_post_not_visible_to_non_follower(self):
        self.client.login(username='non_follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.unlisted_post, response.context['posts'])

    def test_unlisted_post_visible_to_follower(self):
        self.client.login(username='follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.unlisted_post, response.context['posts'])

    def test_unlisted_post_visible_to_friend(self):
        self.client.login(username='friend', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.unlisted_post, response.context['posts'])

    def test_unlisted_post_visible_to_author_on_own_profile(self):
        self.client.login(username='author', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.unlisted_post, response.context['posts'])

    # --- FRIENDS ---

    def test_friends_post_not_visible_to_unauthenticated_user(self):
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.friends_post, response.context['posts'])

    def test_friends_post_not_visible_to_non_follower(self):
        self.client.login(username='non_follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.friends_post, response.context['posts'])

    def test_friends_post_not_visible_to_one_way_follower(self):
        self.client.login(username='follower', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertNotIn(self.friends_post, response.context['posts'])

    def test_friends_post_visible_to_mutual_follower(self):
        self.client.login(username='friend', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.friends_post, response.context['posts'])

    def test_friends_post_visible_to_author_on_own_profile(self):
        self.client.login(username='author', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertIn(self.friends_post, response.context['posts'])

    # --- DELETED ---

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


class NodeAdminDeletedEntriesTest(TestCase):
    """
    Tests for the node-admin deleted entries page (/posts/admin/deleted/).

    User Story: As a node admin, I want deleted entries to stay in the
    database and only be removed from the UI and API, so I can see what
    was deleted.

    Access rules under test:
    - Unauthenticated users are redirected to the login page (302).
    - Authenticated non-staff users receive 403 Forbidden.
    - Staff users (node admins) receive 200 and see all DELETED entries.

    Data-retention rules under test:
    - Soft-deleted entries remain in the database with visibility="DELETED".
    - They are absent from the stream and profile pages for all non-admin users.
    - Staff can also view the full detail page of a deleted entry.
    """

    def setUp(self):
        self.client = Client()

        self.regular_user = User.objects.create_user(
            username='regular', password='pass12345'
        )
        self.admin_user = User.objects.create_user(
            username='nodeadmin', password='pass12345', is_staff=True
        )
        self.author_user = User.objects.create_user(
            username='postauthor', password='pass12345'
        )

        self.live_entry = Entry.objects.create(
            author=self.author_user,
            title='Live Entry',
            content='Still visible',
            content_type='text/plain',
            visibility='PUBLIC',
        )
        self.deleted_entry = Entry.objects.create(
            author=self.author_user,
            title='Deleted Entry',
            content='Was deleted',
            content_type='text/plain',
            visibility='PUBLIC',
        )
        self.deleted_entry.soft_delete()

        self.url = reverse('deleted_entries')

    # ------------------------------------------------------------------
    # Access control: /posts/admin/deleted/
    # ------------------------------------------------------------------

    '''
    Tests: Unauthenticated users cannot access the deleted entries page.
    Pass Condition: Response is a redirect (302) to the login page.
    '''
    def test_unauthenticated_user_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])

    '''
    Tests: A regular (non-staff) authenticated user is denied access.
    Pass Condition: Response status is 403 Forbidden.
    '''
    def test_non_staff_user_gets_403(self):
        self.client.login(username='regular', password='pass12345')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    '''
    Tests: The entry author (non-staff) cannot access the deleted entries page.
    Pass Condition: Response status is 403 Forbidden.
    '''
    def test_entry_author_non_staff_gets_403(self):
        self.client.login(username='postauthor', password='pass12345')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    '''
    Tests: A node admin (is_staff=True) can access the deleted entries page.
    Pass Condition: Response status is 200 OK.
    '''
    def test_staff_user_gets_200(self):
        self.client.login(username='nodeadmin', password='pass12345')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Content: deleted entries page shows correct entries
    # ------------------------------------------------------------------

    '''
    Tests: The deleted entries page contains the soft-deleted entry.
    Pass Condition: deleted_entry is present in the template context.
    '''
    def test_admin_sees_deleted_entry_in_context(self):
        self.client.login(username='nodeadmin', password='pass12345')
        response = self.client.get(self.url)
        self.assertIn(self.deleted_entry, response.context['entries'])

    '''
    Tests: The deleted entries page does NOT show live (non-deleted) entries.
    Pass Condition: live_entry is absent from the template context.
    '''
    def test_admin_does_not_see_live_entry_in_context(self):
        self.client.login(username='nodeadmin', password='pass12345')
        response = self.client.get(self.url)
        self.assertNotIn(self.live_entry, response.context['entries'])

    '''
    Tests: All soft-deleted entries from multiple authors appear on the page.
    Pass Condition: Both deleted entries are present in the template context.
    '''
    def test_admin_sees_deleted_entries_from_all_authors(self):
        other_user = User.objects.create_user(username='other', password='pass12345')
        other_entry = Entry.objects.create(
            author=other_user,
            title='Other Deleted',
            content='Also deleted',
            content_type='text/plain',
        )
        other_entry.soft_delete()

        self.client.login(username='nodeadmin', password='pass12345')
        response = self.client.get(self.url)
        self.assertIn(self.deleted_entry, response.context['entries'])
        self.assertIn(other_entry, response.context['entries'])

    # ------------------------------------------------------------------
    # Data retention: entries stay in DB after soft delete
    # ------------------------------------------------------------------

    '''
    Tests: Soft-deleting an entry does not remove it from the database.
    Pass Condition: Entry still exists in DB with visibility="DELETED".
    '''
    def test_soft_delete_retains_entry_in_database(self):
        entry = Entry.objects.create(
            author=self.author_user,
            title='To Be Deleted',
            content='content',
            content_type='text/plain',
        )
        entry.soft_delete()
        entry.refresh_from_db()
        self.assertEqual(entry.visibility, 'DELETED')
        self.assertTrue(Entry.objects.filter(id=entry.id).exists())

    '''
    Tests: Soft-deleting an entry hides it from the public stream.
    Pass Condition: deleted entry is absent from stream view context.
    '''
    def test_deleted_entry_absent_from_stream(self):
        self.client.login(username='regular', password='pass12345')
        response = self.client.get('/posts/stream/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.deleted_entry, response.context['posts'])

    '''
    Tests: A live entry still appears in the author's own stream after another entry is deleted.
    Pass Condition: live_entry is present in stream view context for its author.
    '''
    def test_live_entry_still_in_stream_after_deletion(self):
        self.client.login(username='postauthor', password='pass12345')
        response = self.client.get('/posts/stream/')
        self.assertIn(self.live_entry, response.context['posts'])

    # ------------------------------------------------------------------
    # Entry detail page: access control for deleted entries
    # ------------------------------------------------------------------

    '''
    Tests: A node admin can open the detail page of a deleted entry.
    Pass Condition: Response status is 200 OK.
    '''
    def test_admin_can_view_deleted_entry_detail(self):
        self.client.login(username='nodeadmin', password='pass12345')
        response = self.client.get(
            reverse('entry_detail', kwargs={'entry_id': self.deleted_entry.id})
        )
        self.assertEqual(response.status_code, 200)

    '''
    Tests: A regular user cannot access the detail page of a deleted entry.
    Pass Condition: Response status is 403 Forbidden.
    '''
    def test_non_staff_cannot_view_deleted_entry_detail(self):
        self.client.login(username='regular', password='pass12345')
        response = self.client.get(
            reverse('entry_detail', kwargs={'entry_id': self.deleted_entry.id})
        )
        self.assertEqual(response.status_code, 403)

    '''
    Tests: The entry author (non-staff) cannot access the detail page of their deleted entry.
    Pass Condition: Response status is 403 Forbidden.
    '''
    def test_author_non_staff_cannot_view_own_deleted_entry_detail(self):
        self.client.login(username='postauthor', password='pass12345')
        response = self.client.get(
            reverse('entry_detail', kwargs={'entry_id': self.deleted_entry.id})
        )
        self.assertEqual(response.status_code, 403)

    '''
    Tests: An unauthenticated user cannot access the detail page of a deleted entry.
    Pass Condition: Response is a redirect (302) to login.
    '''
    def test_unauthenticated_cannot_view_deleted_entry_detail(self):
        response = self.client.get(
            reverse('entry_detail', kwargs={'entry_id': self.deleted_entry.id})
        )
        self.assertEqual(response.status_code, 302)

# REMOTE TESTS
class InboxEntryTests(TestCase):
    """
    Tests for the inbox endpoint handling incoming remote entries.
    Covers create, update, and delete (via visibility=DELETED) from remote nodes.
    """

    def setUp(self):
        self.client = Client()

        # local author who will receive inbox items
        self.local_user = User.objects.create_user(username='local', password='pass12345')
        self.local_author = self.local_user.author

        # remote node credentials
        self.node = RemoteNode.objects.create(
            url='http://remotenode.com/api/',
            username='remoteuser',
            password='remotepass',
            is_active=True,
        )

        # remote author (no local user)
        self.remote_author = Author.objects.create(
            id='http://remotenode.com/api/authors/999',
            host='http://remotenode.com/api/',
            displayName='Remote User',
            user=None,
            is_approved=True,
        )

        from urllib.parse import urlparse
        author_path = urlparse(self.local_author.id).path
        self.inbox_url = f'{author_path}inbox/'

        self.entry_payload = {
            'type': 'entry',
            'id': 'http://remotenode.com/api/authors/999/entries/123',
            'title': 'Remote Entry',
            'content': 'Hello from remote node',
            'contentType': 'text/plain',
            'visibility': 'PUBLIC',
            'published': '2026-01-01T00:00:00+00:00',
            'author': {
                'type': 'author',
                'id': 'http://remotenode.com/api/authors/999',
                'host': 'http://remotenode.com/api/',
                'displayName': 'Remote User',
                'github': None,
                'profileImage': None,
                'web': None,
            }
        }

    def post_to_inbox(self, payload, username='remoteuser', password='remotepass'):
        return self.client.post(
            self.inbox_url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION='Basic ' + __import__('base64').b64encode(
                f'{username}:{password}'.encode()
            ).decode()
        )

    '''
    Tests: inbox creates a new entry when receiving a remote entry object
    Pass Condition: Entry is created in the database with correct fqid
    '''
    def test_inbox_creates_remote_entry(self):
        resp = self.post_to_inbox(self.entry_payload)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Entry.objects.filter(fqid=self.entry_payload['id']).exists())

    '''
    Tests: inbox updates an existing entry when receiving the same entry id again
    Pass Condition: Entry is updated with new content, not duplicated
    '''
    def test_inbox_updates_existing_remote_entry(self):
        self.post_to_inbox(self.entry_payload)

        updated_payload = {**self.entry_payload, 'title': 'Updated Title', 'content': 'Updated content'}
        resp = self.post_to_inbox(updated_payload)
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(Entry.objects.filter(fqid=self.entry_payload['id']).count(), 1)
        entry = Entry.objects.get(fqid=self.entry_payload['id'])
        self.assertEqual(entry.title, 'Updated Title')
        self.assertEqual(entry.content, 'Updated content')

    '''
    Tests: inbox soft deletes an entry when receiving visibility=DELETED
    Pass Condition: Entry visibility is set to DELETED in the database
    '''
    def test_inbox_soft_deletes_remote_entry(self):
        self.post_to_inbox(self.entry_payload)

        deleted_payload = {**self.entry_payload, 'visibility': 'DELETED'}
        resp = self.post_to_inbox(deleted_payload)
        self.assertEqual(resp.status_code, 200)

        entry = Entry.objects.get(fqid=self.entry_payload['id'])
        self.assertEqual(entry.visibility, 'DELETED')

    '''
    Tests: inbox returns 400 when entry payload is missing the id field
    Pass Condition: Response status is 400 Bad Request
    '''
    def test_inbox_rejects_entry_missing_id(self):
        payload = {**self.entry_payload}
        del payload['id']
        resp = self.post_to_inbox(payload)
        self.assertEqual(resp.status_code, 400)

    '''
    Tests: inbox creates a remote author if one does not already exist
    Pass Condition: Author is created in the database with the correct id
    '''
    def test_inbox_creates_remote_author_if_not_exists(self):
        payload = {**self.entry_payload}
        payload['id'] = 'http://remotenode.com/api/authors/999/entries/456'
        payload['author'] = {
            'type': 'author',
            'id': 'http://remotenode.com/api/authors/888/',
            'host': 'http://remotenode.com/api/',
            'displayName': 'Brand New Remote User',
            'github': None,
            'profileImage': None,
            'web': None,
        }
        resp = self.post_to_inbox(payload)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Author.objects.filter(id='http://remotenode.com/api/authors/888/').exists())

    '''
    Tests: fanout sends entry to remote followers' inboxes on post creation
    Pass Condition: requests.post is called once per remote follower
    '''
    def test_fanout_sends_to_remote_followers_on_create(self):
        Follow.objects.create(follower=self.remote_author, followee=self.local_author)

        with patch('posts.views.requests.post') as mock_post:
            self.client.login(username='local', password='pass12345')
            self.client.post(
                '/posts/api/entries/',
                data=json.dumps({
                    'title': 'New Entry',
                    'content': 'hello',
                    'contentType': 'text/plain',
                    'visibility': 'PUBLIC',
                }),
                content_type='application/json',
            )
            self.assertTrue(mock_post.called)

    '''
    Tests: fanout does not send to local followers, only remote ones
    Pass Condition: requests.post is not called when all followers are local
    '''
    def test_fanout_does_not_send_to_local_followers(self):
        local_follower_user = User.objects.create_user(username='localfollower', password='pass12345')
        local_follower_author = local_follower_user.author
        Follow.objects.create(follower=local_follower_author, followee=self.local_author)

        with patch('posts.views.requests.post') as mock_post:
            self.client.login(username='local', password='pass12345')
            self.client.post(
                '/posts/api/entries/',
                data=json.dumps({
                    'title': 'Local Only Entry',
                    'content': 'hello',
                    'contentType': 'text/plain',
                    'visibility': 'PUBLIC',
                }),
                content_type='application/json',
            )
            self.assertFalse(mock_post.called)