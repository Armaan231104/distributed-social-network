# Authors API Documentation

This document describes the API endpoints for the author system, which handles author profiles, following relationships, and follow requests.

## Overview

The author system implements the follow functionality described in the project specification. Authors can follow other authors, and followers must be approved before they can see an author's posts.

Every author has a unique identifier. Local authors use integer IDs (1, 2, 3...) while remote authors use Fully Qualified IDs (FQIDs) such as `http://remote-node.com/api/authors/abc123/`. API endpoints accept either format depending on whether the target author is local or remote.

## Pagination

The following endpoints return paginated results:

- GET /api/authors/{author_id}/following/
- GET /api/authors/{author_id}/followers/
- GET /api/authors/{author_id}/follow_requests/

**Query Parameters:** `page` (default 1), `size` (default 50)

**Response:** `{ "type": "following", "following": [...], "page_number": 1, "size": 50, "count": 150 }`

---
**The following API documentation was generated from Google, Gemini "Generate markdown documentation for the API including request body/params and response body" 2026-02-24**
**Only the endpoint documentation is AI generated in this document, however it reviewed for correctness.**
## API Endpoints

### GET /api/authors/

Returns a list of all approved authors on this node.

**Auth:** None required

**Response:**
```json
{
    "type": "authors",
    "authors": [
        { "type": "author", "id": "http://localhost/api/authors/1/", ... }
    ]
}
```

**User story:** Discover authors to follow

---

### GET /api/authors/{author_id}/

Returns detailed information for a single author.

**Auth:** None required

**Response:** `{ "type": "author", "id": "...", "displayName": "...", ... }`

**User story:** View author profile

---

### GET /api/authors/{author_id}/following/

Returns a list of authors that `{author_id}` is following.

**Auth:** Required

**Pagination:** Supported

**Response:** `{ "type": "following", "following": [...], "page_number": 1, "size": 50, "count": 10 }`

**User story:** See who you follow, list authors to unfollow

---

### GET /api/authors/{author_id}/followers/

Returns a list of authors who follow `{author_id}`.

**Auth:** Required

**Pagination:** Supported

**Response:** `{ "type": "followers", "followers": [...], "page_number": 1, "size": 50, "count": 10 }`

**User story:** See your followers

---

### PUT /api/authors/{author_id}/following/{foreign_id}/

Sends a follow request to another author. Creates a pending follow request that requires approval.

**Auth:** Required

**URL Params:** `author_id` (your ID), `foreign_id` (target author's ID - integer for local, URL-encoded FQID for remote)

**Response:** 201 Created - `{ "status": "follow request sent" }`

**Errors:** 400 if already following or request pending, 403 if unauthorized

**User story:** Follow author (local and remote). For remote authors, your node also sends the request to their inbox.

---

### DELETE /api/authors/{author_id}/following/{foreign_id}/

Removes a follow relationship between two authors. Also clears any pending follow request. If the authors were friends (mutual follows), this also removes the friend status.

**Auth:** Required

**URL Params:** `author_id` (your ID), `foreign_id` (target author's ID)

**Response:** 200 OK - `{ "status": "unfollowed" }`

**User story:** Unfollow author, unfriend author

---

### PUT /api/authors/{author_id}/followers/{foreign_id}/

Accepts a follow request from another author. Creates the follow relationship, allowing the requester to see your posts.

**Auth:** Required

**URL Params:** `author_id` (your ID), `foreign_id` (requester's ID)

**Response:** 200 OK - `{ "status": "follow request accepted" }`

**User story:** Approve follower

---

### DELETE /api/authors/{author_id}/followers/{foreign_id}/

Rejects a pending follow request or removes an existing follower.

**Auth:** Required

**URL Params:** `author_id` (your ID), `foreign_id` (requester's ID)

**Response:** 200 OK - `{ "status": "follower removed" }`

**User story:** Deny follower, remove follower

---

### GET /api/authors/{author_id}/follow_requests/

Returns all pending follow requests for an author.

**Auth:** Required

**Pagination:** Supported

**Response:**
```json
{
    "type": "follow_requests",
    "follow_requests": [
        {
            "type": "follow",
            "summary": "Charlie wants to follow Bob",
            "actor": { "type": "author", ... },
            "object": { "type": "author", ... },
            "status": "pending"
        }
    ],
    "page_number": 1,
    "size": 50,
    "count": 5
}
```

**User story:** See follow requests

---

### POST /api/authors/{author_id}/inbox/

Receives objects from remote nodes, including follow requests. This is how remote nodes send you follow requests.

**Auth:** Cookie auth or HTTP Basic Auth from remote node

**Request Body:**
```json
{
    "type": "follow",
    "summary": "Alice wants to follow Bob",
    "actor": { "type": "author", "id": "http://remote.com/api/authors/1/", ... },
    "object": { "type": "author", "id": "http://localhost/api/authors/2/", ... }
}
```

**Response:** 201 Created

**User story:** Receive remote follow request. After receiving, handle via approve/deny endpoints.

---

## Running Tests

```
python manage.py test accounts.tests
```

This runs all tests covering author model, follow/unfollow API, and follow request workflow.
