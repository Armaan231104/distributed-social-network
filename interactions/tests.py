from django.test import TestCase

from django.test import TestCase, Client
from django.db import IntegrityError
from django.apps import apps
from django.db.models import JSONField
from django.contrib.auth.models import User
from interactions.models import Like, Comment
from posts.models import Entry
from accounts.models import Author
import json


# The following tests were written with assistance from 
# Claude Haiku 4.5, Anthropic, 2026-03-16:


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


class LikeUniquenessConstraintTest(InteractionTestBase):
    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(
            entry=self.entry,
            author=self.author2,
            content='Test comment',
        )

    def test_duplicate_entry_like_raises_error(self):
        """
        Test that an author cannot like the same entry twice at the DB level
        """
        Like.objects.create(author=self.author1, entry=self.entry, comment=None)
        with self.assertRaises(IntegrityError):
            Like.objects.create(author=self.author1, entry=self.entry, comment=None)

    def test_duplicate_comment_like_raises_error(self):
        """
        Test that an author cannot like the same comment twice at the DB level
        """
        Like.objects.create(author=self.author1, entry=None, comment=self.comment)
        with self.assertRaises(IntegrityError):
            Like.objects.create(author=self.author1, entry=None, comment=self.comment)

    def test_two_authors_can_like_same_entry(self):
        """
        Test that two different authors can each like the same entry
        """
        Like.objects.create(author=self.author1, entry=self.entry, comment=None)
        Like.objects.create(author=self.author2, entry=self.entry, comment=None)
        self.assertEqual(Like.objects.filter(entry=self.entry).count(), 2)

    def test_author_can_like_entry_and_comment_independently(self):
        """
        Test that an author can like both an entry and a comment
        """
        Like.objects.create(author=self.author1, entry=self.entry, comment=None)
        Like.objects.create(author=self.author1, entry=None, comment=self.comment)
        self.assertEqual(Like.objects.filter(author=self.author1).count(), 2)

    def test_toggle_like_does_not_create_duplicates(self):
        """
        Test that toggling a like twice doesn't leave duplicate rows
        """
        self.client.login(username='sean', password='test123')
        r1 = self.client.post(f'/interactions/like/entry/{self.entry.id}/')
        self.assertTrue(r1.json()['liked'])
        self.assertEqual(r1.json()['like_count'], 1)

        r2 = self.client.post(f'/interactions/like/entry/{self.entry.id}/')
        self.assertFalse(r2.json()['liked'])
        self.assertEqual(r2.json()['like_count'], 0)
        self.assertEqual(Like.objects.filter(author=self.author1, entry=self.entry).count(), 0)


# ── API Tests ──────────────────────────────────────────────────────────────


class EntryCommentsAPITest(InteractionTestBase):
    """Tests for GET /api/authors/{author_id}/entries/{entry_id}/comments/"""

    def setUp(self):
        super().setUp()
        self.comment1 = Comment.objects.create(
            entry=self.entry, author=self.author2, content='First comment'
        )
        self.comment2 = Comment.objects.create(
            entry=self.entry, author=self.author1, content='Second comment'
        )

    def test_get_entry_comments_returns_200(self):
        """GET comments on a public entry returns 200."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/comments/'
        )
        self.assertEqual(response.status_code, 200)

    def test_get_entry_comments_response_shape(self):
        """Response has correct type, count, and src fields."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/comments/'
        )
        data = response.json()
        self.assertEqual(data['type'], 'comments')
        self.assertEqual(data['count'], 2)
        self.assertIn('src', data)
        self.assertIn('page_number', data)
        self.assertIn('size', data)

    def test_get_entry_comments_content(self):
        """Each comment in src has expected fields."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/comments/'
        )
        data = response.json()
        comment = data['src'][0]
        self.assertEqual(comment['type'], 'comment')
        self.assertIn('id', comment)
        self.assertIn('author', comment)
        self.assertIn('comment', comment)
        self.assertIn('contentType', comment)
        self.assertIn('published', comment)
        self.assertIn('entry', comment)

    def test_get_entry_comments_pagination(self):
        """Pagination query params correctly limit results."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/comments/?page=1&size=1'
        )
        data = response.json()
        self.assertEqual(len(data['src']), 1)
        self.assertEqual(data['count'], 2)

    def test_get_entry_comments_friends_entry_requires_auth(self):
        """Comments on a FRIENDS entry are not accessible to unauthenticated users."""
        friends_entry = Entry.objects.create(
            author=self.user1, title='Friends Only', content='secret', visibility='FRIENDS'
        )
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{friends_entry.id}/comments/'
        )
        self.assertEqual(response.status_code, 403)

    def test_get_entry_comments_nonexistent_entry(self):
        """Returns 404 for a nonexistent entry."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/00000000-0000-0000-0000-000000000000/comments/'
        )
        self.assertEqual(response.status_code, 404)


class CommentDetailAPITest(InteractionTestBase):
    """Tests for GET /api/authors/{author_id}/entries/{entry_id}/comments/{comment_id}/"""

    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(
            entry=self.entry, author=self.author2, content='A comment'
        )

    def test_get_comment_returns_200(self):
        """GET a single comment returns 200."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/comments/{self.comment.id}/'
        )
        self.assertEqual(response.status_code, 200)

    def test_get_comment_response_shape(self):
        """Single comment response has correct fields."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/comments/{self.comment.id}/'
        )
        data = response.json()
        self.assertEqual(data['type'], 'comment')
        self.assertEqual(data['comment'], 'A comment')
        self.assertEqual(data['author']['type'], 'author')

    def test_get_comment_nonexistent(self):
        """Returns 404 for a nonexistent comment."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/comments/00000000-0000-0000-0000-000000000000/'
        )
        self.assertEqual(response.status_code, 404)

    def test_get_comment_wrong_entry(self):
        """Returns 404 when comment does not belong to the given entry."""
        other_entry = Entry.objects.create(
            author=self.user2, title='Other', content='Other', visibility='PUBLIC'
        )
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{other_entry.id}/comments/{self.comment.id}/'
        )
        self.assertEqual(response.status_code, 404)


class AuthorCommentedAPITest(InteractionTestBase):
    """Tests for GET/POST /api/authors/{author_id}/commented/"""

    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(
            entry=self.entry, author=self.author2, content='Aaron commented'
        )

    def test_get_commented_returns_200(self):
        """GET comments by author returns 200."""
        response = self.client.get(f'/api/authors/{self.user2.id}/commented/')
        self.assertEqual(response.status_code, 200)

    def test_get_commented_response_shape(self):
        """Response has correct wrapper shape."""
        response = self.client.get(f'/api/authors/{self.user2.id}/commented/')
        data = response.json()
        self.assertEqual(data['type'], 'comments')
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['src'][0]['comment'], 'Aaron commented')

    def test_get_commented_only_returns_that_authors_comments(self):
        """Only returns comments made by the specified author."""
        Comment.objects.create(entry=self.entry, author=self.author1, content='Sean commented')
        response = self.client.get(f'/api/authors/{self.user2.id}/commented/')
        data = response.json()
        self.assertEqual(data['count'], 1)

    def test_get_commented_pagination(self):
        """Pagination correctly limits results."""
        Comment.objects.create(entry=self.entry, author=self.author2, content='Second comment')
        response = self.client.get(f'/api/authors/{self.user2.id}/commented/?page=1&size=1')
        data = response.json()
        self.assertEqual(len(data['src']), 1)
        self.assertEqual(data['count'], 2)

    def test_post_comment_creates_comment(self):
        """POST to /commented/ creates a new comment."""
        self.client.login(username='aaron', password='test123')
        response = self.client.post(
            f'/api/authors/{self.user2.id}/commented/',
            data=json.dumps({
                'type': 'comment',
                'entry': str(self.entry.id),
                'comment': 'New API comment',
                'contentType': 'text/plain'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Comment.objects.filter(content='New API comment').exists())

    def test_post_comment_requires_auth(self):
        """POST without auth returns 401."""
        response = self.client.post(
            f'/api/authors/{self.user2.id}/commented/',
            data=json.dumps({'entry': str(self.entry.id), 'comment': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    def test_post_comment_missing_fields_returns_400(self):
        """POST without required fields returns 400."""
        self.client.login(username='aaron', password='test123')
        response = self.client.post(
            f'/api/authors/{self.user2.id}/commented/',
            data=json.dumps({'comment': 'no entry field'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_post_comment_invalid_json_returns_400(self):
        """POST with invalid JSON returns 400."""
        self.client.login(username='aaron', password='test123')
        response = self.client.post(
            f'/api/authors/{self.user2.id}/commented/',
            data='not json',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_post_comment_response_shape(self):
        """POST response contains the created comment object."""
        self.client.login(username='aaron', password='test123')
        response = self.client.post(
            f'/api/authors/{self.user2.id}/commented/',
            data=json.dumps({
                'type': 'comment',
                'entry': str(self.entry.id),
                'comment': 'Shape test',
            }),
            content_type='application/json'
        )
        data = response.json()
        self.assertEqual(data['type'], 'comment')
        self.assertEqual(data['comment'], 'Shape test')
        self.assertIn('id', data)
        self.assertIn('author', data)


class CommentedDetailAPITest(InteractionTestBase):
    """Tests for GET /api/authors/{author_id}/commented/{comment_id}/"""

    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(
            entry=self.entry, author=self.author1, content='Specific comment'
        )

    def test_get_commented_detail_returns_200(self):
        """GET a specific comment by author and comment ID returns 200."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/commented/{self.comment.id}/'
        )
        self.assertEqual(response.status_code, 200)

    def test_get_commented_detail_content(self):
        """Response contains the correct comment."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/commented/{self.comment.id}/'
        )
        data = response.json()
        self.assertEqual(data['comment'], 'Specific comment')

    def test_get_commented_detail_wrong_author(self):
        """Returns 404 when comment does not belong to the specified author."""
        response = self.client.get(
            f'/api/authors/{self.user2.id}/commented/{self.comment.id}/'
        )
        self.assertEqual(response.status_code, 404)

    def test_get_commented_detail_nonexistent(self):
        """Returns 404 for a nonexistent comment."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/commented/00000000-0000-0000-0000-000000000000/'
        )
        self.assertEqual(response.status_code, 404)


class EntryLikesAPITest(InteractionTestBase):
    """Tests for GET /api/authors/{author_id}/entries/{entry_id}/likes/"""

    def setUp(self):
        super().setUp()
        self.like = Like.objects.create(author=self.author2, entry=self.entry, comment=None)

    def test_get_entry_likes_returns_200(self):
        """GET likes on a public entry returns 200."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/likes/'
        )
        self.assertEqual(response.status_code, 200)

    def test_get_entry_likes_response_shape(self):
        """Response has correct type, count, and src fields."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/likes/'
        )
        data = response.json()
        self.assertEqual(data['type'], 'likes')
        self.assertEqual(data['count'], 1)
        self.assertIn('src', data)
        self.assertIn('page_number', data)
        self.assertIn('size', data)

    def test_get_entry_likes_content(self):
        """Each like in src has expected fields."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/likes/'
        )
        data = response.json()
        like = data['src'][0]
        self.assertEqual(like['type'], 'like')
        self.assertIn('id', like)
        self.assertIn('author', like)
        self.assertIn('published', like)
        self.assertIn('object', like)

    def test_get_entry_likes_object_is_entry_id(self):
        """The object field on a like points to the entry's ID."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/likes/'
        )
        data = response.json()
        self.assertEqual(data['src'][0]['object'], str(self.entry.id))

    def test_get_entry_likes_friends_entry_requires_auth(self):
        """Likes on a FRIENDS entry are not accessible to unauthenticated users."""
        friends_entry = Entry.objects.create(
            author=self.user1, title='Friends Only', content='secret', visibility='FRIENDS'
        )
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{friends_entry.id}/likes/'
        )
        self.assertEqual(response.status_code, 403)

    def test_get_entry_likes_pagination(self):
        """Pagination query params correctly limit results."""
        Like.objects.create(author=self.author1, entry=self.entry, comment=None)
        response = self.client.get(
            f'/api/authors/{self.user1.id}/entries/{self.entry.id}/likes/?page=1&size=1'
        )
        data = response.json()
        self.assertEqual(len(data['src']), 1)
        self.assertEqual(data['count'], 2)


class AuthorLikedAPITest(InteractionTestBase):
    """Tests for GET /api/authors/{author_id}/liked/"""

    def setUp(self):
        super().setUp()
        self.like = Like.objects.create(author=self.author1, entry=self.entry, comment=None)

    def test_get_author_liked_returns_200(self):
        """GET things liked by an author returns 200."""
        response = self.client.get(f'/api/authors/{self.user1.id}/liked/')
        self.assertEqual(response.status_code, 200)

    def test_get_author_liked_response_shape(self):
        """Response has correct wrapper shape."""
        response = self.client.get(f'/api/authors/{self.user1.id}/liked/')
        data = response.json()
        self.assertEqual(data['type'], 'likes')
        self.assertEqual(data['count'], 1)

    def test_get_author_liked_only_returns_that_authors_likes(self):
        """Only returns likes made by the specified author."""
        Like.objects.create(author=self.author2, entry=self.entry, comment=None)
        response = self.client.get(f'/api/authors/{self.user1.id}/liked/')
        data = response.json()
        self.assertEqual(data['count'], 1)

    def test_get_author_liked_includes_comment_likes(self):
        """Liked list includes likes on comments as well as entries."""
        comment = Comment.objects.create(
            entry=self.entry, author=self.author2, content='A comment'
        )
        Like.objects.create(author=self.author1, comment=comment, entry=None)
        response = self.client.get(f'/api/authors/{self.user1.id}/liked/')
        data = response.json()
        self.assertEqual(data['count'], 2)

    def test_get_author_liked_nonexistent_author(self):
        """Returns 404 for a nonexistent author."""
        response = self.client.get('/api/authors/99999/liked/')
        self.assertEqual(response.status_code, 404)


class LikeDetailAPITest(InteractionTestBase):
    """Tests for GET /api/authors/{author_id}/liked/{like_id}/"""

    def setUp(self):
        super().setUp()
        self.like = Like.objects.create(author=self.author1, entry=self.entry, comment=None)

    def test_get_like_detail_returns_200(self):
        """GET a specific like returns 200."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/liked/{self.like.id}/'
        )
        self.assertEqual(response.status_code, 200)

    def test_get_like_detail_response_shape(self):
        """Response has correct like object shape."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/liked/{self.like.id}/'
        )
        data = response.json()
        self.assertEqual(data['type'], 'like')
        self.assertIn('id', data)
        self.assertIn('author', data)
        self.assertIn('published', data)
        self.assertIn('object', data)

    def test_get_like_detail_wrong_author(self):
        """Returns 404 when like does not belong to the specified author."""
        response = self.client.get(
            f'/api/authors/{self.user2.id}/liked/{self.like.id}/'
        )
        self.assertEqual(response.status_code, 404)

    def test_get_like_detail_nonexistent(self):
        """Returns 404 for a nonexistent like."""
        response = self.client.get(
            f'/api/authors/{self.user1.id}/liked/00000000-0000-0000-0000-000000000000/'
        )
        self.assertEqual(response.status_code, 404)