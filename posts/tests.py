import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

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