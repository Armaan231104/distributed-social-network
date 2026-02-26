from django.urls import path
from . import views, stream

urlpatterns = [
    path("api/entries/create/", views.create_entry),
    path("api/entries/mine/", views.my_entries),
    path("api/entries/<uuid:entry_id>/edit/", views.edit_entry),
    path("api/entries/<uuid:entry_id>/delete/", views.delete_entry),
    path('stream/', stream, name='stream')
]