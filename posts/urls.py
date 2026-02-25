from django.urls import path
from .views import stream

urlpatterns = [
    path('stream/', stream, name='stream')
]