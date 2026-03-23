from rest_framework import serializers
from .models import Author, FollowRequest, Follow

class AuthorSerializer(serializers.ModelSerializer):
    """Serialize Author objects for the API."""
    type = serializers.SerializerMethodField()
    web = serializers.SerializerMethodField()

    class Meta:
        model = Author
        fields = ['type', 'id', 'host', 'displayName', 'github', 'profileImage', 'web']

    def get_type(self, obj):
        return 'author'

    def get_web(self, obj):
        if obj.web:
            return obj.web
        
        # hadle trailing slash too
        author_uuid = str(obj.id).rstrip('/').split('/')[-1]
        return f"/authors/{author_uuid}/"


class AuthorListSerializer(AuthorSerializer):
    """Same as AuthorSerializer, for listing multiple authors."""
    pass


class FollowRequestSerializer(serializers.ModelSerializer):
    """Serialize FollowRequest objects."""
    type = serializers.SerializerMethodField()
    actor = AuthorSerializer(read_only=True)
    object = AuthorSerializer(read_only=True)

    class Meta:
        model = FollowRequest
        # Note: 'status' and 'created_at' are fine to include, remote nodes will just ignore them if they don't need them.
        fields = ['type', 'summary', 'actor', 'object', 'status', 'created_at']

    def get_type(self, obj):
        return 'follow'


class FollowSerializer(serializers.ModelSerializer):
    """Serialize Follow objects."""
    type = serializers.SerializerMethodField()
    follower = AuthorSerializer(read_only=True)
    followee = AuthorSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ['type', 'follower', 'followee', 'created_at']

    def get_type(self, obj):
        return 'follow'
