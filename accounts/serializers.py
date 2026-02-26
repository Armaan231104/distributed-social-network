from rest_framework import serializers
from django.conf import settings
from .models import Author, FollowRequest, Follow


class AuthorSerializer(serializers.ModelSerializer):
    """
    Serializes Author objects to the format specified in the API spec.
    
    The spec requires: type, id, host, displayName, github, profileImage, web
    """
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
        return f"/authors/{obj.id.split('/')[-1]}/"


class AuthorListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing multiple authors in the API response.
    """
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
        return f"/authors/{obj.id.split('/')[-1]}/"


class FollowRequestSerializer(serializers.ModelSerializer):
    """
    Serializes FollowRequest objects to the spec format.
    
    Per spec, follow requests contain:
    - type: "follow"
    - summary: "actor wants to follow object"
    - actor: Author object
    - object: Author object
    """
    type = serializers.SerializerMethodField()
    actor = AuthorSerializer(read_only=True)
    object = AuthorSerializer(read_only=True)

    class Meta:
        model = FollowRequest
        fields = ['type', 'summary', 'actor', 'object', 'status', 'created_at']

    def get_type(self, obj):
        return 'follow'


class FollowRequestCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a follow request from API input.
    Used when receiving follow requests from remote nodes via inbox.
    """
    type = serializers.CharField()
    summary = serializers.CharField()
    actor = AuthorSerializer()
    object = AuthorSerializer()


class FollowSerializer(serializers.ModelSerializer):
    """
    Serializes Follow relationships for the API.
    """
    type = serializers.SerializerMethodField()
    follower = AuthorSerializer(read_only=True)
    followee = AuthorSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ['type', 'follower', 'followee', 'created_at']

    def get_type(self, obj):
        return 'follow'


class FollowersSerializer(serializers.Serializer):
    """
    Serializer for the followers list endpoint.
    Per spec: { "type": "followers", "followers": [...] }
    """
    type = serializers.SerializerMethodField()
    followers = AuthorSerializer(many=True, read_only=True)

    class Meta:
        fields = ['type', 'followers']

    def get_type(self, obj):
        return 'followers'


class FollowingSerializer(serializers.Serializer):
    """
    Serializer for the following list endpoint.
    Per spec: { "type": "following", "following": [...] }
    """
    type = serializers.SerializerMethodField()
    following = AuthorSerializer(many=True, read_only=True)

    class Meta:
        fields = ['type', 'following']

    def get_type(self, obj):
        return 'following'


class InboxFollowSerializer(serializers.Serializer):
    """
    Serializer for parsing incoming follow requests from remote nodes.
    
    Per spec, remote nodes POST follow requests to the inbox endpoint.
    """
    type = serializers.CharField()
    summary = serializers.CharField()
    actor = AuthorSerializer()
    object = AuthorSerializer()
