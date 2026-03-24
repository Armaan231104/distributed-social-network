from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as rf_status
from rest_framework.permissions import IsAdminUser

from .models import RemoteNode
from .forms import RemoteNodeForm


@staff_member_required
def nodes_list(request):
    """
    Display list of connected remote nodes.
    
    Only accessible to staff users (node admins).
    Shows all nodes with options to add, edit, toggle, or remove them.
    """
    nodes = RemoteNode.objects.all()
    return render(request, 'nodes/list.html', {
        'nodes': nodes,
    })


@staff_member_required
def add_node(request):
    """
    Add a new remote node connection.
    
    Handles both GET (show form) and POST (create node) requests.
    """
    if request.method == 'POST':
        form = RemoteNodeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('nodes-list')
    else:
        form = RemoteNodeForm()
    
    return render(request, 'nodes/form.html', {
        'form': form,
        'title': 'Add Node',
        'action': 'Add',
    })


@staff_member_required
def edit_node(request, node_id):
    """
    Edit an existing remote node connection.
    
    Allows updating URL, credentials, or active status.
    """
    node = get_object_or_404(RemoteNode, id=node_id)
    
    if request.method == 'POST':
        form = RemoteNodeForm(request.POST, instance=node)
        if form.is_valid():
            form.save()
            return redirect('nodes-list')
    else:
        form = RemoteNodeForm(instance=node)
    
    return render(request, 'nodes/form.html', {
        'form': form,
        'node': node,
        'title': 'Edit Node',
        'action': 'Save',
    })

@staff_member_required
@require_POST
def delete_node(request, node_id):
    """
    Delete a remote node connection.
    
    Removes the node from the database, stopping all sharing with it.
    """
    node = get_object_or_404(RemoteNode, id=node_id)
    node.delete()
    return redirect('nodes-list')


@staff_member_required
@require_POST
def toggle_node(request, node_id):
    """
    Toggle a node's active status.
    
    Allows enabling or disabling a node connection without deleting it.
    This implements the user story: "I can disable the node to node interfaces 
    for connections that I no longer want, in case another node goes bad."
    """
    node = get_object_or_404(RemoteNode, id=node_id)
    node.is_active = not node.is_active
    node.save(update_fields=['is_active', 'updated_at'])
    return redirect('nodes-list')


class NodeListAPI(APIView):
    """
    API endpoint for listing and creating remote nodes.
    
    GET: List all remote nodes
    POST: Create a new remote node
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        nodes = RemoteNode.objects.all()
        data = {
            'type': 'nodes',
            'nodes': [
                {
                    'id': node.id,
                    'url': node.url,
                    'username': node.username,
                    'is_active': node.is_active,
                    'created_at': node.created_at.isoformat(),
                    'updated_at': node.updated_at.isoformat(),
                }
                for node in nodes
            ]
        }
        return Response(data)

    def post(self, request):
        form = RemoteNodeForm(request.data)
        if form.is_valid():
            node = form.save()
            return Response({
                'id': node.id,
                'url': node.url,
                'message': 'Node added successfully'
            }, status=rf_status.HTTP_201_CREATED)
        return Response(form.errors, status=rf_status.HTTP_400_BAD_REQUEST)


class NodeDetailAPI(APIView):
    """
    API endpoint for managing a single remote node.
    
    GET: Get node details
    PATCH: Update node (e.g., toggle active status)
    DELETE: Remove node
    """
    permission_classes = [IsAdminUser]

    def get(self, request, node_id):
        node = get_object_or_404(RemoteNode, id=node_id)
        data = {
            'id': node.id,
            'url': node.url,
            'username': node.username,
            'is_active': node.is_active,
            'created_at': node.created_at.isoformat(),
            'updated_at': node.updated_at.isoformat(),
        }
        return Response(data)

    def patch(self, request, node_id):
        node = get_object_or_404(RemoteNode, id=node_id)
        
        if 'is_active' in request.data:
            node.is_active = request.data['is_active']
        if 'url' in request.data:
            node.url = request.data['url']
        if 'username' in request.data:
            node.username = request.data['username']
        if 'password' in request.data:
            node.password = request.data['password']
        
        node.save()
        return Response({'message': 'Node updated successfully'})

    def delete(self, request, node_id):
        node = get_object_or_404(RemoteNode, id=node_id)
        node.delete()
        return Response({'message': 'Node deleted successfully'})
