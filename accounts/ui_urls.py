from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
import posts.views

urlpatterns = [
    path('authors/all/', views.authors_list, name='authors-list'),
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
    path('login/', views.login_view, name='login'),    
    path('logout/', views.logout_view, name='logout'),    path('me/edit/', views.edit_profile, name='edit-profile'),
    path('', posts.views.stream, name='home'),
    path('signup/', views.signup_view, name='signup'),
    path('pending-approval/', views.pending_approval, name='pending-approval'),
    path('node-admin/pending-authors/', views.pending_authors_admin, name='pending-authors-admin'),
    path('node-admin/pending-authors/<path:author_id>/approve/', views.approve_author, name='approve-author'),
    path('node-admin/pending-authors/<path:author_id>/reject/', views.reject_author, name='reject-author'),
]
