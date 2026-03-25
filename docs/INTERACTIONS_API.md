```
The following documentation was written with assistance from Claude Haiku 4.5, Anthropic, 2026-03-16:
```
# Interactions API Documentation

The interactions API exposes endpoints for managing comments and likes on entries.
All API endpoints return JSON. Authentication uses Django session auth (login required
for write operations; read access depends on entry visibility).

---

## Visibility Rules

All comment and like endpoints respect the visibility of the entry they are attached to:

- **PUBLIC / UNLISTED** — accessible by anyone, authenticated or not
- **FRIENDS** — accessible only to the entry author or mutual followers (friends)
- **DELETED** — accessible only to node admins (`is_staff`)

If a user does not have access to an entry, any endpoint touching that entry's comments
or likes will return `403 Forbidden`.

---

## Comments

### GET `/api/authors/{author_id}/entries/{entry_id}/comments/`

Returns a paginated list of comments on a specific entry.

**When to use:** When you want to display all comments on an entry, e.g. loading a
comment section.

**Auth:** Not required for PUBLIC/UNLISTED entries. Required for FRIENDS entries.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the entry's author |
| `entry_id` | UUID | The UUID of the entry |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `size` | integer | 5 | Number of comments per page |

**Response:** `200 OK`

```json
{
  "type": "comments",
  "page_number": 1,
  "size": 5,
  "count": 12,
  "src": [
    {
      "type": "comment",
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "author": {
        "type": "author",
        "id": "http://127.0.0.1/api/authors/1/",
        "host": "http://127.0.0.1/api/",
        "displayName": "Greg Johnson",
        "github": "http://github.com/gjohnson",
        "profileImage": "http://127.0.0.1/static/profile_images/greg.jpg",
        "web": "/authors/1/"
      },
      "comment": "Great post!",
      "contentType": "text/plain",
      "published": "2026-03-16T04:00:00+00:00",
      "entry": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"comments"` |
| `page_number` | integer | Current page |
| `size` | integer | Max comments returned on this page |
| `count` | integer | Total number of comments on this entry |
| `src` | array | The comments on this page (see comment object below) |

**Error Responses:**

- `403 Forbidden` — entry is FRIENDS-only and user is not a friend or the author
- `404 Not Found` — entry does not exist

---

### GET `/api/authors/{author_id}/entries/{entry_id}/comments/{comment_id}/`

Returns a single comment on a specific entry.

**When to use:** When you need to fetch or display one specific comment.

**Auth:** Not required for PUBLIC/UNLISTED entries. Required for FRIENDS entries.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the entry's author |
| `entry_id` | UUID | The UUID of the entry |
| `comment_id` | UUID | The UUID of the comment |

**Response:** `200 OK` — a single comment object (same shape as items in `src` above)

```json
{
  "type": "comment",
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "author": {
    "type": "author",
    "id": "http://127.0.0.1/api/authors/1/",
    "host": "http://127.0.0.1/api/",
    "displayName": "Greg Johnson",
    "github": "http://github.com/gjohnson",
    "profileImage": "http://127.0.0.1/static/profile_images/greg.jpg",
    "web": "/authors/1/"
  },
  "comment": "Great post!",
  "contentType": "text/plain",
  "published": "2026-03-16T04:00:00+00:00",
  "entry": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
}
```

**Comment Object Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"comment"` |
| `id` | UUID | Unique identifier for this comment |
| `author` | object | The author who wrote the comment (see author object) |
| `comment` | string | The text content of the comment |
| `contentType` | string | Either `"text/plain"` or `"text/markdown"` |
| `published` | string | ISO 8601 timestamp of when the comment was created |
| `entry` | UUID | The UUID of the entry this comment belongs to |

**Error Responses:**

- `403 Forbidden` — entry is FRIENDS-only and user does not have access
- `404 Not Found` — comment or entry does not exist

---

### GET `/api/authors/{author_id}/commented/`

Returns a paginated list of all comments made by a specific author.

**When to use:** When you want to show a profile view of everything an author has
commented on.

**Auth:** Not required, but unauthenticated users will only see comments on
PUBLIC/UNLISTED entries due to visibility filtering on the comment detail endpoints.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the author |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `size` | integer | 5 | Number of comments per page |

**Response:** `200 OK` — same `comments` wrapper shape as above

**Error Responses:**

- `404 Not Found` — author does not exist

---

### POST `/api/authors/{author_id}/commented/`

Creates a new comment on an entry.

**When to use:** When an authenticated user submits a comment on an entry via an
alternate client (not the web frontend).

**Why not the UI endpoint:** The UI `add_comment` endpoint uses form POST and redirects,
which doesn't work for API clients. This endpoint accepts JSON and returns the created
comment object.

**Auth:** Required. Returns `401` if not authenticated.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the author making the comment |

**Request Body:**

```json
{
  "type": "comment",
  "entry": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "comment": "This is my comment.",
  "contentType": "text/plain"
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entry` | UUID | Yes | UUID of the entry to comment on |
| `comment` | string | Yes | The comment text |
| `contentType` | string | No | `"text/plain"` (default) or `"text/markdown"` |

**Response:** `201 Created` — the created comment object

**Error Responses:**

- `400 Bad Request` — invalid JSON, or missing `entry`/`comment` fields
- `401 Unauthorized` — user is not authenticated
- `403 Forbidden` — user does not have access to the entry
- `404 Not Found` — entry does not exist

---

### GET `/api/authors/{author_id}/commented/{comment_id}/`

Returns a single comment made by a specific author, looked up by comment UUID.

**When to use:** When you have both the author serial and comment UUID and need to
fetch that specific comment.

**Auth:** Not required for PUBLIC/UNLISTED entries. Required for FRIENDS entries.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the author |
| `comment_id` | UUID | The UUID of the comment |

**Response:** `200 OK` — a single comment object

**Error Responses:**

- `403 Forbidden` — entry is FRIENDS-only and user does not have access
- `404 Not Found` — comment does not exist or does not belong to this author

---

## Likes

### GET `/api/authors/{author_id}/entries/{entry_id}/likes/`

Returns a paginated list of likes on a specific entry.

**When to use:** When you want to show who liked an entry, or get a like count with
details.

**Auth:** Not required for PUBLIC/UNLISTED entries. Required for FRIENDS entries.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the entry's author |
| `entry_id` | UUID | The UUID of the entry |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `size` | integer | 50 | Number of likes per page |

**Response:** `200 OK`

```json
{
  "type": "likes",
  "page_number": 1,
  "size": 50,
  "count": 3,
  "src": [
    {
      "type": "like",
      "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "author": {
        "type": "author",
        "id": "http://127.0.0.1/api/authors/2/",
        "host": "http://127.0.0.1/api/",
        "displayName": "Lara Croft",
        "github": "http://github.com/laracroft",
        "profileImage": "http://127.0.0.1/static/profile_images/lara.jpg",
        "web": "/authors/2/"
      },
      "published": "2026-03-16T05:00:00+00:00",
      "object": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"likes"` |
| `page_number` | integer | Current page |
| `size` | integer | Max likes returned on this page |
| `count` | integer | Total number of likes on this entry |
| `src` | array | The likes on this page (see like object below) |

**Like Object Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"like"` |
| `id` | UUID | Unique identifier for this like |
| `author` | object | The author who made the like |
| `published` | string | ISO 8601 timestamp of when the like was created |
| `object` | UUID | UUID of the entry or comment that was liked |

**Error Responses:**

- `403 Forbidden` — entry is FRIENDS-only and user does not have access
- `404 Not Found` — entry does not exist

---

### GET `/api/authors/{author_id}/liked/`

Returns a paginated list of everything a specific author has liked (entries and comments).

**When to use:** When displaying a profile view of an author's activity, or checking
what content an author has engaged with.

**Auth:** Not required.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the author |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `size` | integer | 50 | Number of likes per page |

**Response:** `200 OK` — same `likes` wrapper shape as above

**Note:** The `object` field in each like will be the UUID of either an entry or a
comment depending on what was liked. There is currently no type indicator on the object
field — use the liked endpoint alongside entry/comment endpoints to determine the type.

**Error Responses:**

- `404 Not Found` — author does not exist

---

### GET `/api/authors/{author_id}/liked/{like_id}/`

Returns a single like made by a specific author.

**When to use:** When you have a specific like UUID and need its full details.

**Auth:** Not required.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `author_id` | string | The serial ID of the author |
| `like_id` | UUID | The UUID of the like |

**Response:** `200 OK` — a single like object

**Error Responses:**

- `404 Not Found` — like does not exist or does not belong to this author

---

## Author Object

All endpoints that return comments or likes include a nested author object:

```json
{
  "type": "author",
  "id": "http://127.0.0.1/api/authors/1/",
  "host": "http://127.0.0.1/api/",
  "displayName": "Greg Johnson",
  "github": "http://github.com/gjohnson",
  "profileImage": "http://127.0.0.1/static/profile_images/greg.jpg",
  "web": "/authors/1/"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"author"` |
| `id` | URL | The author's FQID |
| `host` | URL | The host node's API base URL |
| `displayName` | string | The author's display name |
| `github` | URL | The author's GitHub profile URL, if set |
| `profileImage` | URL | URL of the author's profile image, if set |
| `web` | URL | The author's profile page URL |

---

## Pagination

All list endpoints (`comments`, `likes`) are paginated. Use the `page` and `size`
query parameters to navigate:

```
GET /api/authors/1/entries/b2c3d4.../comments/?page=2&size=10
```

The response always includes `count` (total items) so you can calculate the number
of pages: `ceil(count / size)`.

---

# GitHub Activity Integration

## Overview

The system integrates with the GitHub Events API to automatically generate entries from an author's public GitHub activity. This allows user profiles to reflect development activity as posts within the platform.

This feature can be triggered manually via an API endpoint and also runs automatically as a background task.

---

## Endpoint

### Trigger GitHub Sync

```
POST /posts/api/github/sync/{author_id}/
```

**Purpose:**  
Manually triggers synchronization of GitHub activity for a specific author.

**Auth:** Required (must be the author or an admin)

---

## URL Parameters

| Parameter | Type | Description |
|----------|------|-------------|
| `author_id` | string | The ID of the author whose GitHub activity will be synced |

---

## Response

### Success (200 OK)

```json
{
  "status": "sync completed",
  "entries_created": 3
}
```

| Field | Type | Description |
|------|------|-------------|
| `status` | string | Indicates sync completion |
| `entries_created` | integer | Number of new entries generated |

---

## Behavior

- Fetches public events from the GitHub API  
- Processes only `PushEvent` types  
- Ignores unsupported event types  
- Creates entries only for new events (prevents duplicates)  
- Generated entries are always marked as `PUBLIC`

---

## Data Processing

For each valid `PushEvent`:

- Extract repository name  
- Extract commit messages  
- Extract event timestamp  
- Construct a formatted entry  

### Example Generated Entry

```json
{
  "title": "GitHub Activity: user/repo",
  "content": "- Fix authentication bug\n- Refactor API routes",
  "contentType": "text/plain",
  "visibility": "PUBLIC"
}
```
---

## Inbox: Receiving Remote Entries (Including Images)

The inbox endpoint also handles entries sent from remote nodes.  
This allows nodes to share posts, including image posts, across the distributed network.

---

### Endpoint

POST /api/authors/{author_id}/inbox/

---

### Supported Object Type

"type": "entry"

---

### Example Request (Text Entry)

    {
      "type": "entry",
      "id": "http://remote-node.com/api/authors/999/entries/123",
      "title": "Remote Post",
      "content": "Hello world",
      "contentType": "text/plain",
      "visibility": "PUBLIC",
      "author": {
        "type": "author",
        "id": "http://remote-node.com/api/authors/999",
        "host": "http://remote-node.com/api/",
        "displayName": "Remote Author"
      }
    }

---

### Example Request (Image Entry - Base64)

    {
      "type": "entry",
      "id": "http://remote-node.com/api/authors/999/entries/124",
      "title": "Image Post",
      "contentType": "image/png;base64",
      "content": "<base64-encoded-image>",
      "visibility": "PUBLIC",
      "author": {
        "type": "author",
        "id": "http://remote-node.com/api/authors/999",
        "host": "http://remote-node.com/api/",
        "displayName": "Remote Author"
      }
    }

---

### Behavior

- The inbox accepts entry objects from remote nodes
- The entry is identified using its FQID (`id`)
- If the entry does not exist, it is created
- If the entry already exists, it is updated (no duplication)
- If visibility is set to "DELETED", the entry is soft deleted

---

### Image Handling

When `contentType` contains "base64":

- The `content` field is treated as a base64-encoded image
- The image is decoded into a file
- The file is stored locally
- The entry is created with:
  - empty text content
  - an attached image file

---

### Remote Author Handling

If the incoming author does not exist:

- A new remote author is created
- The author is stored using their FQID
- No local user is associated with this author

---

### Entry Synchronization

The inbox ensures consistency across nodes:

- Create → new entry stored using FQID  
- Update → existing entry updated without duplication  
- Delete → entry visibility set to "DELETED"  

---

### Fan-out Behavior

When a local entry is created:

- The system sends the entry to all remote followers
- Each remote node receives the entry through its inbox

Local followers do NOT trigger remote requests.

---

## Execution Model

- Runs automatically in the background at regular intervals (~20 seconds)  
- Can also be triggered manually via the endpoint above  
- Does not block normal API requests or user interactions  

---

## Deduplication Strategy

- Each GitHub event is tracked using its unique event ID  
- Previously processed events are skipped  
- Ensures no duplicate entries are created across sync cycles  

---

## Requirements

- Author must have a valid GitHub profile URL configured  
- GitHub activity must be public  

---

## Limitations

- Only `PushEvent` is supported  
- No support for private repositories  
- No webhook integration (polling-based system)  
- Subject to GitHub API rate limits  

---