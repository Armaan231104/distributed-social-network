from django.urls import path
from . import views
from interactions import views as interaction_views

urlpatterns = [
    path("api/entries/", views.create_entry),
    path("api/entries/mine/", views.my_entries),
    path("api/entries/<uuid:entry_id>/", views.entry_detail_api),
    path("api/entries/stream/", views.stream_api, name="stream_api"),
    path("api/authors/<path:author_id>/entries/<uuid:entry_id>/image/", views.entry_image),

    path('stream/', views.stream, name='stream'),
    path('entry/<uuid:entry_id>/', views.entry_detail, name='entry_detail'),
    path("entry/<uuid:entry_id>/delete/", views.delete_entry_ui, name="delete_entry_ui"),
    path("api/images/upload/", views.upload_hosted_image, name="upload_hosted_image"),
    path("admin/deleted/", views.deleted_entries, name="deleted_entries"),
]