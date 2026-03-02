from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('authors/all/', views.authors_list, name='authors-list'),
    path('authors/<path:author_id>/profile/', views.author_profile, name='author-profile'),
    path('follow/<path:author_id>/', views.follow_author, name='follow-author'),
    path('unfollow/<path:author_id>/', views.unfollow_author, name='unfollow-author'),
    path('follow-requests/', views.follow_requests, name='follow-requests'),
    path('follow-requests/<int:request_id>/accept/', views.accept_follow_request, name='accept-follow-request'),
    path('follow-requests/<int:request_id>/reject/', views.reject_follow_request, name='reject-follow-request'),
    path('me/', views.my_profile, name='my-profile'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('me/edit/', views.edit_profile, name='edit-profile'),
]
