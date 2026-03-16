from rest_framework import serializers
from .models import Comment, Like
from accounts.serializers import AuthorSerializer


class LikeSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    author = AuthorSerializer(read_only=True)
    object = serializers.SerializerMethodField()
    published = serializers.DateTimeField(source='created_at')

    class Meta:
        model = Like
        fields = ['type', 'id', 'author', 'published', 'object']

    def get_type(self, obj):
        return 'like'

    def get_object(self, obj):
        if obj.entry:
            return str(obj.entry.id)
        if obj.comment:
            return str(obj.comment.id)
        return None


class CommentSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    comment = serializers.CharField(source='content')
    published = serializers.DateTimeField(source='created_at')
    author = AuthorSerializer(read_only=True)
    entry = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['type', 'id', 'author', 'comment', 'contentType', 'published', 'entry']

    def get_type(self, obj):
        return 'comment'

    def get_entry(self, obj):
        return str(obj.entry.id)


def serialize_likes(likes_queryset, page=1, size=50):
    paginated = likes_queryset[(page - 1) * size: page * size]
    return {
        "type": "likes",
        "page_number": page,
        "size": size,
        "count": likes_queryset.count(),
        "src": LikeSerializer(paginated, many=True).data
    }


def serialize_comments(comments_queryset, page=1, size=5):
    paginated = comments_queryset[(page - 1) * size: page * size]
    return {
        "type": "comments",
        "page_number": page,
        "size": size,
        "count": comments_queryset.count(),
        "src": CommentSerializer(paginated, many=True).data
    }