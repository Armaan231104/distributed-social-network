# Posts API Documentation

This document describes the API endpoints for the posts system which handles entry creation, editing, deletion, visibility enforcement, and direct link access.

Entries support multiple visibility levels and content types. Access control is enforced according to visibility rules and user authentication status.

All Entry identifiers are UUIDs.

---

## Overview

Each Entry has:
- A UUID identifier
- A local Django User as author
- A visibility level
- A content type
- A published timestamp
- Optional image upload

Visibility rules determine who can access an entry via API or UI.

---

## Data Model

### Entry Fields

| Field | Type | Example | Purpose |
|-------|------|---------|---------|
| id | UUID | `550e8400-e29b-41d4-a716-446655440000` | Unique identifier for the entry |
| author | User (ForeignKey) | user id `5` | The local user who created the entry |
| title | string (max 200 chars) | `"My First Post"` | Title of the entry |
| content | string | `"Hello world"` | Body content |
| content_type | string (choice) | `"text/plain"` | Defines how content is interpreted |
| visibility | string (choice) | `"PUBLIC"` | Determines who can access the entry |
| published_at | datetime (ISO 8601) | `"2026-02-27T15:00:00Z"` | Timestamp automatically set at creation |
| image | file (optional) | `entries/photo.png` | Image file for image posts |

---

## Visibility Levels

### PUBLIC
- Accessible by anyone
- No authentication required
- Can be shared via direct link
- Appears in public streams

### UNLISTED
- Accessible by anyone with the direct link
- No authentication required
- Does not appear in public listings

### FRIENDS
- Accessible only to the author
- Requires authentication
- Returns 403 Forbidden for other users

### DELETED
- Only accessible to node administrators (`is_staff = True`)
- Returns 404 Not Found for non-admin users
- Authors cannot view their own deleted entries

---

## Supported Content Types

| Value | Meaning |
|-------|---------|
| text/plain | Plain text |
| text/markdown | CommonMark markdown |
| image | Image upload |

Invalid content types return 400 Bad Request.

---

# API Endpoints

Base path:

/posts/api/

---

## 1. Create Entry

POST /posts/api/entries/create/

Creates a new entry.

Authentication Required: Yes

### JSON Request (Text Entries)

Example:

```json
{
  "title": "My Post",
  "content": "Hello world",
  "contentType": "text/plain",
  "visibility": "PUBLIC"
}
```

Request Fields:

| Field | Type | Required | Example | Purpose |
|-------|------|----------|---------|---------|
| title | string | Yes | `"My Post"` | Title of entry |
| content | string | Yes | `"Hello world"` | Body content |
| contentType | string | Yes | `"text/plain"` | Must match supported types |
| visibility | string | No | `"PUBLIC"` | Defaults to PUBLIC |

Success Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Response Codes:
- 201 Created
- 400 Bad Request (invalid JSON)
- 400 Bad Request (invalid contentType)

When to use:
Use for creating text or markdown entries.

When not to use:
Do not use JSON format for image uploads.

---

### Multipart Request (Image Posts)

Used for image uploads.

Required fields:
- title (string)
- content (optional caption)
- contentType = "image"
- image (file upload)

Success Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 2. Get Entry by ID

GET /posts/api/entries/{entry_id}/

Returns entry details.

Example Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "My Post",
  "content": "Hello world",
  "contentType": "text/plain",
  "visibility": "PUBLIC",
  "published": "2026-02-27T15:00:00Z"
}
```

Response Codes:
- 200 OK
- 403 Forbidden (FRIENDS accessed by non-author)
- 404 Not Found (DELETED accessed by non-admin)

When to use:
Use when accessing an entry via direct link.

---

## 3. Get My Entries

GET /posts/api/entries/mine/

Authentication Required: Yes

Returns all entries created by the authenticated user. Deleted entries are excluded.

Example Response:

```json
[
  {
    "id": "uuid",
    "title": "My Post",
    "content": "Text",
    "contentType": "text/plain",
    "visibility": "PUBLIC",
    "published": "2026-02-27T15:00:00Z"
  }
]
```

---

## 4. Edit Entry

PUT /posts/api/entries/{entry_id}/edit/

Authentication Required: Yes  
Only the author may edit.

Example Request:

```json
{
  "title": "Updated Title",
  "content": "Updated content",
  "contentType": "text/plain"
}
```

Success Response:

```json
{
  "updated": true
}
```

Response Codes:
- 200 OK
- 403 Forbidden (not author)
- 404 Not Found (DELETED entry)
- 400 Bad Request (invalid contentType)

---

## 5. Delete Entry (Soft Delete)

DELETE /posts/api/entries/{entry_id}/delete/

Authentication Required: Yes  
Only the author may delete.

Success Response:

```json
{
  "deleted": true
}
```

Behavior:
- Sets visibility to "DELETED"
- Entry remains stored in database
- Only staff users can access afterward

Response Codes:
- 200 OK
- 403 Forbidden (not author)
- 400 Bad Request (wrong method)

---

## UI Endpoints

GET /posts/stream/

Unauthenticated users:
- See PUBLIC entries only

Authenticated users:
- See their own entries (excluding DELETED)
- See PUBLIC and UNLISTED entries from followed authors
- See FRIENDS entries only if mutual following

Deleted entries never appear in stream.

---

## User Stories Supported

- A reader can share a public or unlisted entry via direct link
- Authors cannot modify other authors’ entries
- Authors can delete their own entries
- Deleted entries are visible only to node administrators
- Authors can see their own entries until deleted
- Node admin can host multiple authors on the node