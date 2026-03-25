# Posts API Documentation

This document describes the API endpoints for the posts system which handles entry creation, editing, deletion, visibility enforcement, direct link access, and stream retrieval.

Entries support multiple visibility levels and content types. Access control is enforced according to visibility rules and user authentication status.

Entries are identified using both a UUID (`id`) and a Fully Qualified ID (`fqid`).

- The UUID is used locally within the node
- The FQID is used for communication between nodes

---

## Overview

Each Entry has:

- A UUID identifier
- A local Django User as author
- A visibility level
- A content type
- A published timestamp
- An updated timestamp
- Optional image upload

Visibility rules determine who can access an entry via API or UI.

Entries may appear:

- on an author's profile page
- in the stream page
- through direct API access by ID
- through the stream API

Deleted entries remain in the database but are hidden from normal users.

---

# Data Model

## Entry Fields

| Field | Type | Example | Purpose |
|------|------|------|------|
| id | UUID | `550e8400-e29b-41d4-a716-446655440000` | Unique identifier for the entry |
| author | User (ForeignKey) | user id `5` | The local user who created the entry |
| title | string (max 200 chars) | `"My First Post"` | Title of the entry |
| content | string | `"Hello world"` | Body content |
| content_type | string (choice) | `"text/plain"` | Defines how content is interpreted |
| visibility | string (choice) | `"PUBLIC"` | Determines who can access the entry |
| published_at | datetime (ISO 8601) | `"2026-02-27T15:00:00Z"` | Timestamp automatically set at creation |
| updated_at | datetime (ISO 8601) | `"2026-02-27T15:05:00Z"` | Timestamp updated when edited |
| image | file (optional) | `entries/photo.png` | Image file for image posts |

---

## Entry Identifiers (FQID)

Entries use two identifiers:

- `id` → UUID (local database identifier)
- `fqid` → Fully Qualified ID (global identifier)

### FQID Format

http://<host>/api/authors/<author_id>/entries/<entry_id>


### Example


http://127.0.0.1:8000/api/authors/1/entries/550e8400-e29b-41d4-a716-446655440000
...


### Purpose

The UUID (`id`) is used internally by the node.

The FQID (`fqid`) is used for:

- communication between nodes
- inbox delivery
- remote storage of entries

### Behavior

- Local entries generate an FQID on save
- Remote entries use the FQID provided by the sending node
- Inbox operations always match entries using FQID

This ensures entries remain globally unique across nodes.

---

# Visibility Levels

## PUBLIC

- Accessible by anyone
- No authentication required
- Can be shared via direct link
- Appears in public streams

## UNLISTED

- Accessible by anyone with the direct link
- No authentication required
- Does not appear in public listings
- Appears in the stream of authors who follow the entry author

## FRIENDS

- Accessible to the author
- Requires authentication
- Accessible to authors who mutually follow the entry author
- Returns **403 Forbidden** for users who are not friends with the author

## DELETED

- Only accessible to node administrators (`is_staff = True`)
- Returns **404 Not Found** for non-admin users
- Authors cannot view their own deleted entries
- Does not appear in profile pages or streams

---

# Supported Content Types

| Value | Meaning |
|------|------|
| text/plain | Plain text |
| text/markdown | CommonMark markdown |
| image | Image upload |

Invalid content types return **400 Bad Request**.

---

## Image Posts

The system supports image-based entries in addition to text and markdown.

### Creating Image Posts

Image posts must be submitted using:


multipart/form-data


Required fields:

- `title`
- `contentType = "image"`
- `image` (file upload)
- optional `content` (caption)

### Example Request

Form data:


title = "My Image"
content = "Caption"
contentType = "image"
image = <file>

### Remote Image Support

In addition to file uploads, images may also be received from remote nodes via the inbox as base64-encoded content.

These images are:

- decoded into files
- stored locally
- attached to entries automatically

### Behavior

- The uploaded file is stored on the server
- The entry is created with:
  - `content_type = "image"`
  - associated image file
- The text content is used as a caption

### Validation Rules

- Missing image file → `400 Bad Request`
- Invalid contentType → `400 Bad Request`

### Storage

Images are stored under:


/media/entries/


and linked to the entry record.

---

# API Endpoints

Base path

```
/posts/api/
```

---

# 1. Create Entry

```
POST /posts/api/entries/
```

Creates a new entry. Allows users to create entries with different content types, including:
- text/plain (plain text)
- text/markdown (CommonMark)
- image (image upload)

Behavior
- Users can select the type of post they want to create.
- The backend validates the contentType field against supported types.
- Image posts must be submitted using multipart/form-data.
- Text and markdown posts must be submitted as JSON

Authentication Required: **Yes**

---

## JSON Request (Text Entries)

Example

```json
{
  "title": "My Post",
  "content": "Hello world",
  "contentType": "text/plain",
  "visibility": "PUBLIC"
}
```

### Request Fields

| Field | Type | Required | Example | Purpose |
|------|------|------|------|------|
| title | string | Yes | `"My Post"` | Title of entry |
| content | string | Yes | `"Hello world"` | Body content |
| contentType | string | Yes | `"text/plain"` | Must match supported types |
| visibility | string | No | `"PUBLIC"` | Defaults to PUBLIC |

### Success Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response Codes

- 201 Created
- 400 Bad Request (invalid JSON)
- 400 Bad Request (invalid contentType)
- 400 Bad Request (invalid visibility)

---

## Multipart Request (Image Posts)

Used for image uploads.

Required fields:

- title
- content (optional caption)
- contentType = `"image"`
- image file upload

Example response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

# 2. Upload Hosted Image (For Commonmark Embedding)

POST /posts/api/images/

Authentication Required: **Yes**

Example response

{
  "id": "uuid",
  "url": "http://localhost/media/hosted_images/example.png"
}

Behavior
- The uploaded image is stored on the node.
- A publicly accessible URL is generated.
- This URL can be inserted into CommonMark content using standard markdown syntax:

![alt text](image_url)

- This enables inline image rendering within markdown posts.

## Response Codes
- 201 Created
- 400 Bad Request (missing image)
- 400 Bad Request (invalid request method)

-- 

# 3. Get Entry by ID

```
GET /posts/api/entries/{entry_id}/
```

Returns entry details.

### Example Response

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

### Response Codes

- 200 OK
- 403 Forbidden (FRIENDS accessed by non-author)
- 404 Not Found (DELETED accessed by non-admin)

---

# 4. Get My Entries

```
GET /posts/api/entries/mine/
```

Authentication Required: **Yes**

Returns all entries created by the authenticated user.

Deleted entries are excluded.

### Example Response

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

# 5. Get Stream Entries

```
GET /posts/api/entries/stream/
```

Authentication Required: **No**

Returns entries that should appear in the user's stream.

### Behavior

Unauthenticated users receive:

- PUBLIC entries only

Authenticated users receive:

- their own entries (excluding DELETED)
- all PUBLIC entries known to the node
- UNLISTED entries from authors they follow
- FRIENDS entries from mutual followers

Deleted entries are never returned.

Entries are returned **newest first**.

### Example Response

```json
{
  "type": "entries",
  "count": 2,
  "src": [
    {
      "id": "uuid",
      "title": "Example",
      "content": "Hello world",
      "contentType": "text/plain",
      "visibility": "PUBLIC",
      "published": "2026-03-16T12:00:00Z",
      "updated": "2026-03-16T12:05:00Z",
      "isEdited": true
    }
  ]
}
```

---

# 6. Edit Entry (Partial Update)

```
PATCH /posts/api/entries/{entry_id}/
```

Authentication Required: **Yes**

Only the author may edit. This is a partial update - only fields provided will be updated.

### Example Request

```json
PATCH /posts/api/entries/{entry_id}/
{
  "title": "Updated Title",
  "content": "Updated content"
}
```

### Success Response

```json
{
  "updated": true
}
```

### Response Codes

- 200 OK
- 403 Forbidden
- 404 Not Found
- 400 Bad Request

---

# 7. Delete Entry (Soft Delete)

```
DELETE /posts/api/entries/{entry_id}/
```

Authentication Required: **Yes**

Only the author may delete.

### Success Response

```json
{
  "deleted": true
}
```

### Behavior

- Sets visibility to `"DELETED"`
- Entry remains stored in the database
- Only staff users can access afterward
- Deleted entries do not appear in streams or profiles

### Response Codes

- 200 OK
- 403 Forbidden
- 400 Bad Request

---

# UI Endpoints

## Stream Page

```
GET /posts/stream/
```

Unauthenticated users:

- See PUBLIC entries only

Authenticated users:

- See their own entries (excluding DELETED)
- See all PUBLIC entries known to the node
- See UNLISTED entries from followed authors
- See FRIENDS entries from mutual followers

Deleted entries never appear in the stream.

Entries are shown **newest first**.

Edited entries show their **latest version**.

---

## Entry Detail Page

```
GET /posts/entry/{entry_id}/
```

Returns the entry detail page if the user is allowed to access the entry.

If the user is not permitted to view the entry, access is denied.

---

## Delete Entry via UI

```
POST /posts/entry/{entry_id}/delete/
```

Authentication Required: **Yes**

Only the author may delete.

If successful, the entry is soft deleted

---

## Admin: View Deleted Entries

```
GET /posts/admin/deleted/
```

Authentication Required: **Yes** (staff only)

Lists all soft-deleted entries across all authors, ordered by most recently deleted first

### Access Control

Must be authenticated (unauthenticated users are redirected to login)

Must be a node admin(`is_staff = True`)

Non-staff authenticated users receive **403 Forbidden**

### Behavior

Displays all entries where `visibility = "DELETED"`

Entries are never hard-deleted; this is the only UI location where deleted entries are visible

Results are ordered by `updated_at` descending (most recently deleted first)

### Response Codes

200 OK (staff user)

302 Found (unauthenticated - redirects to login)

403 Forbidden (authenticated but no staff)
