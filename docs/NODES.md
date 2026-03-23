# Nodes API Documentation

This document describes the API and UI endpoints for managing connections to remote nodes in the distributed social network.

## Overview

Remote nodes represent other servers in the distributed network. Node admins can add, edit, and remove node connections. Each connection stores the URL and credentials needed for HTTP Basic Authentication when communicating with that remote node.

## User Stories Implemented

1. **Connect to remote nodes** - Enter URL + username + password to connect
2. **Add nodes to share with** - CRUD operations on node records
3. **Remove nodes** - Delete node from database
4. **Prevent nodes without valid credentials** - Middleware validates incoming Basic Auth
5. **HTTP Basic Auth for node-to-node** - Same middleware handles authentication
6. **Disable node-to-node interfaces** - Toggle `is_active` to enable/disable connections

---

## Data Model

### RemoteNode Fields

| Field | Type | Description |
|-------|------|-------------|
| id | AutoField | Primary key |
| url | URLField | Base URL of remote node (unique) |
| username | CharField | Username for HTTP Basic Auth |
| password | CharField | Password for HTTP Basic Auth |
| is_active | BooleanField | Whether node can connect |
| created_at | DateTimeField | Creation timestamp |
| updated_at | DateTimeField | Last update timestamp |

---

## UI Endpoints

### Node Management Page

```
GET /nodes/
```

Displays all connected nodes with options to add, edit, toggle, or remove them.

**Access:** Staff users only (node admins)

**Response:** HTML page with node list

---

### Add Node

```
GET /nodes/add/
```

Form to add a new remote node connection.

**Access:** Staff users only

**Fields:**
- `url` - Base URL (e.g., https://other-node.herokuapp.com)
- `username` - Username for authentication
- `password` - Password for authentication
- `is_active` - Whether connection is enabled

---

### Edit Node

```
GET /nodes/<node_id>/edit/
```

Form to edit an existing node connection.

**Access:** Staff users only

---

### Delete Node

```
POST /nodes/<node_id>/delete/
```

Remove a node connection.

**Access:** Staff users only

**Response:** Redirects to node list

---

### Toggle Node

```
POST /nodes/<node_id>/toggle/
```

Enable or disable a node connection without deleting.

**Access:** Staff users only

**Response:** Redirects to node list

---

## API Endpoints

### List Nodes

```
GET /nodes/api/
```

Returns all remote nodes.

**Authentication:** Admin only (session auth)

**Response (200):**
```json
{
  "type": "nodes",
  "nodes": [
    {
      "id": 1,
      "url": "https://other-node.herokuapp.com",
      "username": "admin",
      "is_active": true,
      "created_at": "2026-03-23T12:00:00Z",
      "updated_at": "2026-03-23T12:00:00Z"
    }
  ]
}
```

---

### Add Node

```
POST /nodes/api/
```

Create a new remote node connection.

**Authentication:** Admin only

**Request Body:**
```json
{
  "url": "https://other-node.herokuapp.com",
  "username": "admin",
  "password": "secretpassword",
  "is_active": true
}
```

**Response (201):**
```json
{
  "id": 1,
  "url": "https://other-node.herokuapp.com",
  "message": "Node added successfully"
}
```

**Response (400):** Validation errors

---

### Get Node

```
GET /nodes/api/<node_id>/
```

Returns details of a specific node.

**Authentication:** Admin only

**Response (200):**
```json
{
  "id": 1,
  "url": "https://other-node.herokuapp.com",
  "username": "admin",
  "is_active": true,
  "created_at": "2026-03-23T12:00:00Z",
  "updated_at": "2026-03-23T12:00:00Z"
}
```

---

### Update Node

```
PATCH /nodes/api/<node_id>/
```

Update node fields (e.g., toggle active status).

**Authentication:** Admin only

**Request Body:**
```json
{
  "is_active": false
}
```

**Response (200):**
```json
{
  "message": "Node updated successfully"
}
```

---

### Delete Node

```
DELETE /nodes/api/<node_id>/
```

Remove a node connection.

**Authentication:** Admin only

**Response (200):**
```json
{
  "message": "Node deleted successfully"
}
```

---

## Node-to-Node Authentication

When remote nodes connect to this node's API, they must provide HTTP Basic Authentication.

### Incoming Requests

The system validates credentials against:
1. Stored `RemoteNode` records with matching username and active status
2. This node's own credentials from settings (`NODE_USERNAME`, `NODE_PASSWORD`)

### Outgoing Requests

When this node sends requests to remote nodes, it uses credentials stored in the `RemoteNode` model.

---

## Settings

The following settings control node-to-node authentication:

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| NODE_USERNAME | NODE_USERNAME | admin | Username for this node |
| NODE_PASSWORD | NODE_PASSWORD | node_password_change_me | Password for this node |

These credentials should be set in the environment or in the settings file and documented in README.md for other nodes to use when connecting.

---

## Integration with Other Features

### Sending to Remote Nodes

The `RemoteNode` model provides helper methods for outgoing requests:

```python
from nodes.models import RemoteNode

# Get credentials for a remote host
node = RemoteNode.objects.filter(
    url__startswith=target_host,
    is_active=True
).first()

if node:
    # Use node.username and node.password for Basic Auth
    response = requests.post(
        f"{node.url}/api/authors/{author_id}/inbox/",
        json=data,
        auth=(node.username, node.password)
    )
```

### Disabling a Node

When a node is disabled (`is_active=False`), the system will:
- Reject incoming requests from that node (authentication fails)
- Skip sending outgoing requests to that node

This implements the user story: "I can disable the node to node interfaces for connections that I no longer want, in case another node goes bad."
