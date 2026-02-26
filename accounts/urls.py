from django.urls import path, re_path
from . import views

apiurlpatterns = [
    # API endpoints
    path('authors/', views.AuthorListView.as_view(), name='author-list'),
    path('authors/<str:author_id>/', views.AuthorDetailView.as_view(), name='author-detail'),
    path('authors/<str:author_id>/following/', views.FollowingListView.as_view(), name='author-following'),
    path('authors/<str:author_id>/following/<path:foreign_id>/', views.FollowView.as_view(), name='author-follow'),
    path('authors/<str:author_id>/followers/', views.FollowersListView.as_view(), name='author-followers'),
    path('authors/<str:author_id>/followers/<path:foreign_id>/', views.AcceptFollowView.as_view(), name='author-followers-manage'),
    path('authors/<str:author_id>/follow_requests/', views.FollowRequestListView.as_view(), name='author-follow-requests'),
    path('authors/<str:author_id>/inbox/', views.InboxView.as_view(), name='author-inbox'),
]

uiurlpatterns = [
    # UI endpoints
    path('authors/all/', views.authors_list, name='authors-list'),
    path('authors/<path:author_id>/profile/', views.author_profile, name='author-profile'),
    path('follow/<path:author_id>/', views.follow_author, name='follow-author'),
    path('unfollow/<path:author_id>/', views.unfollow_author, name='unfollow-author'),
    path('follow-requests/', views.follow_requests, name='follow-requests'),
    path('follow-requests/<int:request_id>/accept/', views.accept_follow_request, name='accept-follow-request'),
    path('follow-requests/<int:request_id>/reject/', views.reject_follow_request, name='reject-follow-request'),
    path('me/', views.my_profile, name='my-profile'),
]

urlpatterns = apiurlpatterns + uiurlpatterns
