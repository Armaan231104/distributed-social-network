```
The following documentation was written with assistance from Claude Haiku 4.5, Anthropic, 2026-03-02:
```
---

# Interactions UI

## Overview

The Interactions UI endpoints handle likes and comments on entries (posts) and comments. All endpoints require authentication.

**Access Control**: Users can only interact with entries they can see:
- PUBLIC/UNLISTED: Anyone with a link can like/comment
- FRIENDS: Only the author and their friends can like/comment
- DELETED: No interactions allowed

---

## Endpoints

### 1. Toggle Like

`POST /interactions/like/<object_type>/<object_id>/`

**Purpose**: Like or unlike an entry or comment.

**Usage**: 
- User hits like button → makes POST request → like toggles (creates if doesn't exist, deletes if exists)
- Works optimistically: don't need to check current state first

**Why**: Simple toggle is more elegant than separate like/unlike endpoints.

**URL Parameters**:
- `object_type` (string): `"entry"` or `"comment"`
- `object_id` (UUID): ID of the target

**Response** (200 OK):
```json
{
  "liked": true,
  "like_count": 5
}
```

| Field | Type | Purpose |
|-------|------|---------|
| `liked` | boolean | `true` if like was created, `false` if deleted |
| `like_count` | integer | Total likes on object after toggle |

**Examples**:

Like an entry (first time):
```
POST /interactions/like/entry/550e8400-e29b-41d4-a716-446655440000/
→ 200 { "liked": true, "like_count": 5 }
```

Unlike the same entry:
```
POST /interactions/like/entry/550e8400-e29b-41d4-a716-446655440000/
→ 200 { "liked": false, "like_count": 4 }
```

Like a comment:
```
POST /interactions/like/comment/f47ac10b-58cc-4372-a567-0e02b2c3d479/
→ 200 { "liked": true, "like_count": 2 }
```

**Errors**:
- `400 Bad Request`: Invalid `object_type` (must be "entry" or "comment")
- `403 Forbidden`: User can't access this entry (visibility/permission issue)
- `404 Not Found`: Entry/comment doesn't exist

**Notes**:
- Database prevents duplicate likes via unique constraint on (author, entry) and (author, comment)
- Requires authentication
- When liking a comment, checks parent entry's visibility, not the comment's

---

### 2. Add Comment

`POST /posts/entry/<entry_id>/comment/`

**Purpose**: Post a comment on an entry.

**Usage**:
- User fills comment form → submits → creates comment and redirects to entry detail page
- New comment appears in the list below the entry

**Why**: Enables conversation/engagement on posts.

**URL Parameters**:
- `entry_id` (UUID or string): Entry to comment on

**Request Body**:
```
content=<text>
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `content` | string | Yes | Comment text (cannot be empty) |

**Response** (302 Found):
Redirects to `/posts/entry/<entry_id>/` where the new comment is visible.

**Examples**:

Add a comment:
```
POST /posts/entry/550e8400-e29b-41d4-a716-446655440000/comment/
Body: content=Great post!
→ 302 redirect to /posts/entry/550e8400-e29b-41d4-a716-446655440000/
```

Comment appears on entry detail page with:
- Author's display name
- Current timestamp
- Comment text

**Errors**:
- `403 Forbidden`: User can't access this entry
- `404 Not Found`: Entry doesn't exist
- No error for empty content—silently ignored (consider field validation in form)

**Notes**:
- Requires authentication
- Author is automatically set to `request.user.author`
- Timestamp auto-generated (can't override)
- Comments ordered by creation time (oldest first)
- No edit/delete endpoints exist

---

## Data Models

**Like**:
```python
id: UUID
author: Author (who liked it)
entry: Entry or null (post liked)
comment: Comment or null (comment liked)
created_at: DateTime
# Constraint: Must have either entry OR comment (not both)
```

**Comment**:
```python
id: UUID
entry: Entry (post being commented on)
author: Author (who wrote it)
content: TextField
created_at: DateTime
```

---

## Implementation Notes

- **Likes are immutable**: Create or delete only, never update
- **Comments are permanent**: Created entries stay until manually deleted (no soft-delete)
- **Cascade delete**: Deleting an entry deletes all its comments and likes
- **No pagination**: Like/comment counts fetched with entry data (fine for typical post sizes)

---

# Account Approval & Authentication UI

## Overview

These endpoints handle user login, pending approval flow, and admin approval/rejection of authors. Newly registered users must be approved before accessing full system functionality.

---

## GET `/pending-approval/`

Displays the pending approval page for users who are not yet approved.

**Auth:** Required

---

### Behavior

- Retrieves the logged-in user's associated `Author`
- If no author exists → redirects to login
- If `is_approved = True` → redirects to home
- Otherwise → renders pending approval page

---

### Response

- `200 OK` — renders `pending_approval.html`
- `302 Redirect` → `/login/` (no author found)
- `302 Redirect` → `/home/` (already approved)

---

## GET `/pending-authors/`

Displays a list of authors awaiting approval (admin view).

**Auth:** Required  
**Access:** Staff only

---

### Behavior

- Requires authenticated user with `is_staff = True`
- Fetches all authors where:
  - `is_approved = False`
  - `user` is not null
- Returns admin dashboard view

---

### Response

- `200 OK` — renders `pending_authors_admin.html`
- `403 Forbidden` — non-admin access

---

## GET `/pending-authors-admin/`

Alternative admin endpoint for viewing pending authors.

**Auth:** Required  
**Access:** Staff only

---

### Behavior

- Requires approved author + staff privileges
- Fetches all unapproved authors
- Renders admin approval interface

---

### Response

- `200 OK` — renders `pending_authors_admin.html`
- `403 Forbidden` — non-admin access

---

## POST `/approve-author/{author_id}/`

Approves a pending author.

**Auth:** Required  
**Access:** Staff only

---

### URL Parameters

| Parameter | Type | Description |
|----------|------|-------------|
| `author_id` | integer | ID of the author to approve |

---

### Behavior

- Verifies user is staff
- Retrieves author by ID
- Sets `is_approved = True`
- Saves author
- Redirects to admin pending authors page

---

### Response

- `302 Redirect` → `/pending-authors-admin/`
- `403 Forbidden` — non-admin access
- `404 Not Found` — author does not exist

---

## POST `/reject-author/{author_id}/`

Rejects and deletes a pending author.

**Auth:** Required  
**Access:** Staff only

---

### URL Parameters

| Parameter | Type | Description |
|----------|------|-------------|
| `author_id` | integer | ID of the author to reject |

---

### Behavior

- Verifies user is staff
- Retrieves author by ID
- If linked user exists → deletes user (cascades author)
- Otherwise → deletes author directly
- Redirects to admin pending authors page

---

### Response

- `302 Redirect` → `/pending-authors-admin/`
- `403 Forbidden` — non-admin access
- `404 Not Found` — author does not exist

---

## POST `/login/`

Authenticates a user and redirects based on approval status.

**Auth:** Not required

---

### Request (Form Data)

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `username` | string | Yes | User's username |
| `password` | string | Yes | User's password |

---

### Behavior

- Validates credentials using Django `AuthenticationForm`
- Logs user in if valid
- If user is staff → redirects to home
- If user has no author → redirects to login
- If author is not approved → redirects to pending approval page
- Otherwise → redirects to home

---

### Response

- `302 Redirect` → `/home/` (approved user or staff)
- `302 Redirect` → `/pending-approval/` (not approved)
- `302 Redirect` → `/login/` (no author)
- `200 OK` — form re-rendered with errors

---

## Notes

- Approval system enforces moderation before access  
- Only staff users can approve/reject authors  
- Authentication uses Django session-based login  
- Users without approval cannot access full platform features  

---