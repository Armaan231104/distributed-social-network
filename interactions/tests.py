from django.test import TestCase

from django.test import TestCase, Client
from django.contrib.auth.models import User
from interactions.models import Like, Comment
from posts.models import Entry
from accounts.models import Author
import json


class InteractionTestBase(TestCase):
    """
    Base class with common setup for interaction tests. Run with:
    % python manage.py test interactions
    """
    def setUp(self):
        self.client = Client()

        self.user1 = User.objects.create_user(username='sean', password='test123')
        self.author1 = self.user1.author

        self.user2 = User.objects.create_user(username='aaron', password='test123')
        self.author2 = self.user2.author

        self.entry = Entry.objects.create(
            author=self.user1,
            title='Test Entry',
            content='Test content',
            visibility='PUBLIC',
        )


class LikeEntryTest(InteractionTestBase):
    def test_like_entry_requires_auth(self):
        """
        Test that unauthorized user cannot like an entry
        """
        response = self.client.post(f'/interactions/like/entry/{self.entry.id}/')
        self.assertEqual(response.status_code, 302)  # redirect to login

    def test_like_entry(self):
        """ 
        Test that liking entries works 
        """
        self.client.login(username='sean', password='test123')
        response = self.client.post(f'/interactions/like/entry/{self.entry.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)
        self.assertTrue(Like.objects.filter(author=self.author1, entry=self.entry).exists())

    def test_unlike_entry(self):
        """
        Test that unliking entries works
        """
        Like.objects.create(author=self.author1, entry=self.entry, comment=None)
        self.client.login(username='sean', password='test123')
        response = self.client.post(f'/interactions/like/entry/{self.entry.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['liked'])
        self.assertEqual(data['like_count'], 0)
        self.assertFalse(Like.objects.filter(author=self.author1, entry=self.entry).exists())

    def test_like_entry_updates_count(self):
        """
        Test that entry can be liked multiple times
        """
        Like.objects.create(author=self.author2, entry=self.entry, comment=None)
        self.client.login(username='sean', password='test123')
        response = self.client.post(f'/interactions/like/entry/{self.entry.id}/')
        data = response.json()
        self.assertEqual(data['like_count'], 2)

    def test_like_nonexistent_entry(self):
        """
        Test that liking an entry that doesn't exist returns an error
        """
        self.client.login(username='sean', password='test123')
        response = self.client.post('/interactions/like/entry/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)

    def test_like_invalid_type(self):
        """
        Test that liking an invalid type returns an error
        """
        self.client.login(username='sean', password='test123')
        response = self.client.post(f'/interactions/like/invalid/{self.entry.id}/')
        self.assertEqual(response.status_code, 400)

    def test_like_requires_post_method(self):
        """
        Test that using like with a non-post method returns an error
        """
        self.client.login(username='sean', password='test123')
        response = self.client.get(f'/interactions/like/entry/{self.entry.id}/')
        self.assertEqual(response.status_code, 405)


class LikeCommentTest(InteractionTestBase):
    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(
            entry=self.entry,
            author=self.author2,
            content='Test comment'
        )

    def test_like_comment_requires_auth(self):
        """
        Test that unauthorized user can't like a comment
        """
        response = self.client.post(f'/interactions/like/comment/{self.comment.id}/')
        self.assertEqual(response.status_code, 302)

    def test_like_comment(self):
        """
        Test that liking a comment works"""
        self.client.login(username='sean', password='test123')
        response = self.client.post(f'/interactions/like/comment/{self.comment.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)
        self.assertTrue(Like.objects.filter(author=self.author1, comment=self.comment).exists())

    def test_unlike_comment(self):
        """
        Test that unliking a comment works
        """
        Like.objects.create(author=self.author1, comment=self.comment, entry=None)
        self.client.login(username='sean', password='test123')
        response = self.client.post(f'/interactions/like/comment/{self.comment.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['liked'])
        self.assertEqual(data['like_count'], 0)
        self.assertFalse(Like.objects.filter(author=self.author1, comment=self.comment).exists())

    def test_like_nonexistent_comment(self):
        """
        Test that liking a nonexistent comment returns an error
        """
        self.client.login(username='sean', password='test123')
        response = self.client.post('/interactions/like/comment/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)

    def test_like_comment_does_not_affect_entry_likes(self):
        """
        Test that liking a comment doesn't affect the entry's like count
        """
        self.client.login(username='sean', password='test123')
        self.client.post(f'/interactions/like/comment/{self.comment.id}/')
        self.assertEqual(Like.objects.filter(entry=self.entry).count(), 0)


class CommentTest(InteractionTestBase):
    def test_add_comment_requires_auth(self):
        """
        test that unauthorized user cannot add comment
        """
        response = self.client.post(
            f'/posts/entry/{self.entry.id}/comment/',
            {'content': 'Test comment'}
        )
        self.assertEqual(response.status_code, 302)

    def test_add_comment(self):
        """
        Test that making a comment works
        """
        self.client.login(username='aaron', password='test123')
        response = self.client.post(
            f'/posts/entry/{self.entry.id}/comment/',
            {'content': 'Test comment'}
        )
        self.assertEqual(response.status_code, 302)  # redirects to entry_detail
        self.assertTrue(Comment.objects.filter(
            entry=self.entry,
            author=self.author2,
            content='Test comment'
        ).exists())

    def test_add_empty_comment_does_not_save(self):
        """
        Test that adding an empty comment does not save it
        """
        self.client.login(username='aaron', password='test123')
        self.client.post(
            f'/posts/entry/{self.entry.id}/comment/',
            {'content': ''}
        )
        self.assertEqual(Comment.objects.filter(entry=self.entry).count(), 0)

    def test_add_comment_to_nonexistent_entry(self):
        """
        Test that adding a comment to nonexistent entry returns an error
        """
        self.client.login(username='aaron', password='test123')
        response = self.client.post(
            '/posts/entry/00000000-0000-0000-0000-000000000000/comment/',
            {'content': 'Test comment'}
        )
        self.assertEqual(response.status_code, 404)

    def test_multiple_comments_on_entry(self):
        """
        Test that multiple comments can be added to the same entry
        """
        self.client.login(username='sean', password='test123')
        self.client.post(f'/posts/entry/{self.entry.id}/comment/', {'content': 'First comment'})
        self.client.post(f'/posts/entry/{self.entry.id}/comment/', {'content': 'Second comment'})
        self.assertEqual(Comment.objects.filter(entry=self.entry).count(), 2)

    def test_comment_author_is_logged_in_user(self):
        """
        Test that comment can be tracked by logged in user
        """
        self.client.login(username='aaron', password='test123')
        self.client.post(f'/posts/entry/{self.entry.id}/comment/', {'content': 'Test comment'})
        comment = Comment.objects.get(entry=self.entry)
        self.assertEqual(comment.author, self.author2)

    def test_add_comment_requires_post_method(self):
        """
        Test that calling add comment with non-post method doesn't work
        """
        self.client.login(username='aaron', password='test123')
        response = self.client.get(f'/posts/entry/{self.entry.id}/comment/')
        self.assertNotEqual(response.status_code, 200)


class CommentModelTest(InteractionTestBase):
    def test_comment_creation(self):
        """
        Test that commment creation works properly
        """
        comment = Comment.objects.create(
            entry=self.entry,
            author=self.author1,
            content='Test comment'
        )
        self.assertEqual(comment.content, 'Test comment')
        self.assertEqual(comment.entry, self.entry)
        self.assertEqual(comment.author, self.author1)

    def test_comment_ordering(self):
        """
        Test that comment ordering works properly
        """
        comment1 = Comment.objects.create(entry=self.entry, author=self.author1, content='First')
        comment2 = Comment.objects.create(entry=self.entry, author=self.author2, content='Second')
        comments = Comment.objects.filter(entry=self.entry)
        self.assertEqual(comments[0], comment1)
        self.assertEqual(comments[1], comment2)

    def test_comment_deleted_with_entry(self):
        """
        Test that deleting the entry a comment is attached to also deletes the comment
        """
        Comment.objects.create(entry=self.entry, author=self.author1, content='Test')
        self.entry.delete()
        self.assertEqual(Comment.objects.count(), 0)


class LikeModelTest(InteractionTestBase):
    def test_like_entry_creation(self):
        """
        Test that likes on an entry are created properly
        """
        like = Like.objects.create(author=self.author1, entry=self.entry, comment=None)
        self.assertEqual(like.author, self.author1)
        self.assertEqual(like.entry, self.entry)
        self.assertIsNone(like.comment)

    def test_like_comment_creation(self):
        """
        Test that likes on a comment are created properly
        """
        comment = Comment.objects.create(entry=self.entry, author=self.author2, content='Test')
        like = Like.objects.create(author=self.author1, comment=comment, entry=None)
        self.assertEqual(like.comment, comment)
        self.assertIsNone(like.entry)

    def test_like_deleted_with_entry(self):
        """
        Test that likes attached to an entry are deleted when the entry is deleted
        """
        Like.objects.create(author=self.author1, entry=self.entry, comment=None)
        self.entry.delete()
        self.assertEqual(Like.objects.count(), 0)

    def test_like_deleted_with_comment(self):
        """
        Test that likes attached to a comment are deleted when the comment is deleted
        """
        comment = Comment.objects.create(entry=self.entry, author=self.author2, content='Test')
        Like.objects.create(author=self.author1, comment=comment, entry=None)
        comment.delete()
        self.assertEqual(Like.objects.count(), 0)
