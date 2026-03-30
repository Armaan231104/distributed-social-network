from django.urls import path, re_path, include
import accounts.views as views
import posts.views
import interactions.views as interaction_views

apiurlpatterns = [
    path('api/authors/', views.AuthorListView.as_view(), name='author-list'),
    path('api/authors/<path:author_id>/inbox/', views.InboxView.as_view(), name='author-inbox'),
    path('api/authors/<path:author_id>/following/', views.FollowingListView.as_view(), name='author-following-api'),
    path('api/authors/<path:author_id>/entries/', posts.views.AuthorEntriesView.as_view(), name='author-entries-api'),
    path('api/authors/<path:author_id>/following/<path:foreign_id>/', views.FollowView.as_view(), name='author-follow-api'),
    path('api/authors/<path:author_id>/followers/', views.FollowersListView.as_view(), name='author-followers-api'),
    path('api/authors/<path:author_id>/followers/<path:foreign_id>/', views.AcceptFollowView.as_view(), name='author-followers-manage-api'),
    path('api/authors/<path:author_id>/friends/', views.FriendsListView.as_view(), name='author-friends-api'),
    path('api/authors/<path:author_id>/follow_requests/', views.FollowRequestListView.as_view(), name='author-follow-requests'),
    # Interactions API - comments (required by spec)
    path('api/authors/<str:author_id>/entries/<str:entry_id>/comments/', interaction_views.EntryCommentsView.as_view()),
    path('api/authors/<str:author_id>/entries/<str:entry_id>/comments/<uuid:comment_id>/', interaction_views.CommentDetailView.as_view()),
    path('api/authors/<str:author_id>/commented/', interaction_views.AuthorCommentedView.as_view()),
    path('api/authors/<str:author_id>/commented/<uuid:comment_id>/', interaction_views.CommentedDetailView.as_view()),
    # Interactions API - likes (required by spec)
    path('api/authors/<str:author_id>/entries/<str:entry_id>/likes/', interaction_views.EntryLikesView.as_view()),
    path('api/authors/<str:author_id>/liked/', interaction_views.AuthorLikedView.as_view()),
    path('api/authors/<str:author_id>/liked/<uuid:like_id>/', interaction_views.LikeDetailView.as_view()),
    # ugly but helps to avoid regex matching things it is not supposed to
    re_path(r'^api/authors/(?P<author_id>(?:https?://[^/]+.*/api/authors/[^/]+/?|[^/]+))/$', views.AuthorDetailView.as_view(), name='author-detail'),
]

uiurlpatterns = [
    path('authors/all/', views.authors_list, name='authors-list'),
    path('follow-remote/', views.follow_remote_author, name='follow-remote'),
    path('authors/<path:author_id>/profile/', views.author_profile, name='author-profile'),
    path('authors/<path:author_id>/followers/', views.author_followers, name='author-followers'),
    path('authors/<path:author_id>/following/', views.author_following, name='author-following'),
    path('authors/<path:author_id>/friends/', views.author_friends, name='author-friends'),
    
    path('follow/<path:author_id>/', views.follow_author, name='follow-author'),
    path('unfollow/<path:author_id>/', views.unfollow_author, name='unfollow-author'),
    path('cancel-request/<path:author_id>/', views.cancel_follow_request, name='cancel-follow-request'),
    
    path('follow-requests/', views.follow_requests, name='follow-requests'),
    path('follow-requests/<int:request_id>/accept/', views.accept_follow_request, name='accept-follow-request'),
    path('follow-requests/<int:request_id>/reject/', views.reject_follow_request, name='reject-follow-request'),
    
    path('me/', views.my_profile, name='my-profile'),
    path('me/edit/', views.edit_profile, name='edit-my-profile'),
    path('authors/<path:author_id>/edit/', views.edit_profile, name='edit-profile'), #This is important. DO NOT REMOVE
    
    path('login/', views.login_view, name='login'),    
    path('logout/', views.logout_view, name='logout'),    
    path('signup/', views.signup_view, name='signup'),
    
    path('pending-approval/', views.pending_approval, name='pending-approval'),
    path('node-admin/pending-authors/', views.pending_authors_admin, name='pending-authors-admin'),
    path('node-admin/pending-authors/<path:author_id>/approve/', views.approve_author, name='approve-author'),
    path('node-admin/pending-authors/<path:author_id>/reject/', views.reject_author, name='reject-author'),
    
    path('', posts.views.stream, name='home'),
]

# Combine them for Django to read
urlpatterns = apiurlpatterns + uiurlpatterns
