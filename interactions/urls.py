from django.urls import path
from . import views

urlpatterns = [
    path('like/<str:object_type>/<uuid:object_id>/', views.toggle_like, name='toggle-like'),
]
