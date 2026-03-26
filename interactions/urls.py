from django.urls import path
from . import views

urlpatterns = [
    # UI
    path('like/<str:object_type>/<uuid:object_id>/', views.toggle_like, name='toggle-like'),
    path('entry/<path:entry_id>/comment/', views.add_comment, name='add_comment'),

    # API - comments
    path('api/authors/<path:author_id>/entries/<path:entry_id>/comments/', views.EntryCommentsView.as_view()),
    path('api/authors/<path:author_id>/entries/<path:entry_id>/comments/<uuid:comment_id>/', views.CommentDetailView.as_view()),
    path('api/authors/<path:author_id>/commented/', views.AuthorCommentedView.as_view()),
    path('api/authors/<path:author_id>/commented/<uuid:comment_id>/', views.CommentedDetailView.as_view()),

    # API - likes
    path('api/authors/<path:author_id>/entries/<path:entry_id>/likes/', views.EntryLikesView.as_view()),
    path('api/authors/<path:author_id>/liked/', views.AuthorLikedView.as_view()),
    path('api/authors/<path:author_id>/liked/<uuid:like_id>/', views.LikeDetailView.as_view()),
]