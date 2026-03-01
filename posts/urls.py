from django.urls import path
from . import views

urlpatterns = [
    path("api/entries/create/", views.create_entry),
    path("api/entries/mine/", views.my_entries),
    path("api/entries/<uuid:entry_id>/", views.get_entry),
    path("api/entries/<uuid:entry_id>/edit/", views.edit_entry),
    path("api/entries/<uuid:entry_id>/delete/", views.delete_entry),
    path("entries/<uuid:entry_id>/", views.entry_detail, name="entry_detail"),
    path("entries/<uuid:entry_id>/delete/", views.delete_entry_ui, name="delete_entry_ui"),
    path('stream/', views.stream, name='stream')
]