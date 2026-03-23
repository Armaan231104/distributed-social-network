from django.urls import path
from . import views

urlpatterns = [
    path('', views.nodes_list, name='nodes-list'),
    path('add/', views.add_node, name='add-node'),
    path('<int:node_id>/edit/', views.edit_node, name='edit-node'),
    path('<int:node_id>/delete/', views.delete_node, name='delete-node'),
    path('<int:node_id>/toggle/', views.toggle_node, name='toggle-node'),
    path('api/', views.NodeListAPI.as_view(), name='node-list-api'),
    path('api/<int:node_id>/', views.NodeDetailAPI.as_view(), name='node-detail-api'),
]
