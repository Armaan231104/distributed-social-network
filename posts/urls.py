from django.urls import path
from . import views
from interactions import views as interaction_views

urlpatterns = [
    path("api/entries/create/", views.create_entry),
    path("api/entries/<uuid:entry_id>/update/", views.update_entry, name="update_entry"),
    path("api/entries/<uuid:entry_id>/", views.get_entry),
    path("api/entries/<uuid:entry_id>/edit/", views.edit_entry),
    path("api/entries/<uuid:entry_id>/delete/", views.delete_entry),

    path('stream/', views.stream, name='stream'),
    path('entry/<uuid:entry_id>/', views.entry_detail, name='entry_detail'),
    path('entry/<str:entry_id>/comment/', interaction_views.add_comment, name='add_comment'),
    path("entry/<uuid:entry_id>/delete/", views.delete_entry_ui, name="delete_entry_ui"),
    path("api/images/upload/", views.upload_hosted_image, name="upload_hosted_image"),
    path("admin/deleted/", views.deleted_entries, name="deleted_entries"),
]