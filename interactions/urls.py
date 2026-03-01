from django.urls import path
from . import views

urlpatterns = [
    path('like/<uuid:entry_id>/', views.toggle_like, name='toggle-like'),
]
