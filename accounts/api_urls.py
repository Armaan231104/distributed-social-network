from django.urls import path
from . import views

urlpatterns = [
    path('authors/', views.AuthorListView.as_view(), name='author-list'),
    path('authors/<int:author_id>/', views.AuthorDetailView.as_view(), name='author-detail'),
    path('authors/<int:author_id>/following/', views.FollowingListView.as_view(), name='author-following'),
    path('authors/<int:author_id>/following/<int:foreign_id>/', views.FollowView.as_view(), name='author-follow'),
    path('authors/<int:author_id>/followers/', views.FollowersListView.as_view(), name='author-followers'),
    path('authors/<int:author_id>/followers/<int:foreign_id>/', views.AcceptFollowView.as_view(), name='author-followers-manage'),
    path('authors/<int:author_id>/follow_requests/', views.FollowRequestListView.as_view(), name='author-follow-requests'),
    path('authors/<int:author_id>/inbox/', views.InboxView.as_view(), name='author-inbox'),
]
