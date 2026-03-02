# Authors API Documentation

This document describes the API endpoints for the author system, which handles author profiles, following relationships, and follow requests.

## Overview

The author system implements the follow functionality described in the project specification. Authors can follow other authors, and followers must be approved before they can see an author's posts.

Every author has a unique identifier. Local authors use integer IDs (1, 2, 3...) while remote authors use Fully Qualified IDs (FQIDs) such as `http://remote-node.com/api/authors/abc123/`. API endpoints accept either format depending on whether the target author is local or remote.

## Authentication

Endpoints that modify data require authentication. You can authenticate using:
- Session authentication (via browser login)
- Basic authentication (HTTP Basic Auth header)
- Token authentication (Token header)

Public read-only endpoints (listing authors, viewing profiles) do not require authentication.

## Pagination

The following endpoints return paginated results. Pagination is required by the spec for list endpoints to handle large datasets efficiently.

**Endpoints that support pagination:**
- GET /api/authors/{author_id}/following/
- GET /api/authors/{author_id}/followers/
- GET /api/authors/{author_id}/follow_requests/

**Query Parameters:**
- `page`: Page number (1-indexed, default: 1)
- `size`: Items per page (default: 50)

**Response Format:**
```json
{
    "type": "following",
    "items": [
        { "type": "author", "id": "...", ... }
    ],
    "page_number": 1,
    "size": 50,
    "count": 150
}
```

The response includes `page_number` (current page), `size` (items per page), and `count` (total items across all pages). Use the `page` and `size` query parameters to navigate through results. For example, `?page=2&size=10` returns the second page with 10 items per page.

---

## API Endpoints

### GET /api/authors/

Returns a list of all approved authors on this node. This is the starting point for discovering authors to follow.

**Auth:** None required - public endpoint

**Pagination:** Not paginated. Returns all approved authors in a single response.

**User Stories:** This endpoint is used in stories #1 and #2. Before a user can follow someone, they need to see who exists on the node. Your application fetches this list to display authors that users can choose to follow. Call this endpoint when rendering the "Find Authors" or "Discover" page.

---

### GET /api/authors/{author_id}/

Returns detailed information for a single author identified by their ID.

**Auth:** None required - public endpoint

**Pagination:** Not applicable - returns single object

**User Stories:** Used when displaying an author's profile page. Required for stories #3, #4, and #5 to show the target author's information. Call this endpoint when the user navigates to a profile page.

---

### GET /api/authors/{author_id}/following/

Returns a list of authors that `{author_id}` is following. These are the authors whose posts will appear in the user's stream.

**Auth:** Required. The authenticated user must match `{author_id}`.

**Pagination:** Supported. Use `page` and `size` query parameters. For example, `?page=1&size=20` returns the first 20 authors being followed.

**User Stories:** 
- **#5 (Unfollow):** Your UI should call this endpoint to show users who they're currently following. Present this list to the user and allow them to click "unfollow" on any author. Call this when the user visits their "Following" page or when showing options to unfollow.

---

### GET /api/authors/{author_id}/followers/

Returns a list of authors who follow `{author_id}`. These authors receive the user's posts in their stream.

**Auth:** Required. The authenticated user must match `{author_id}`.

**Pagination:** Supported. Use `page` and `size` query parameters.

**User Stories:**
- **#3 (Approve/Deny):** Before approving or denying a follower, the UI may want to show who already follows the user. Call this endpoint to display the current follower list alongside pending requests.

---

### PUT /api/authors/{author_id}/following/{foreign_id}/

Sends a follow request to another author. This is the primary endpoint for initiating a follow relationship.

When called, it creates a follow request with "pending" status. The request is not immediately active - the target author must approve it first. This matches the spec requirement that follow requests go to the inbox and require approval before the follow relationship is established.

For local authors, pass the integer ID (e.g., `2`). For remote authors, pass the URL-encoded FQID (e.g., `http%3A%2F%2Fremote-node.com%2Fapi%2Fauthors%2Fabc%2F`).

**Auth:** Required. The authenticated user must be `{author_id}`.

**Pagination:** Not applicable.

**Response Codes:**
- 201: Follow request created successfully
- 400: Already following this author, or a request is already pending
- 403: Not authenticated as the specified author
- 404: Target author does not exist

**User Stories:**
- **#1 (Follow local author):** Call this endpoint with the authenticated user's ID and the target local author's ID. Example: Alice (ID 1) wants to follow Bob (ID 2) → PUT /api/authors/1/following/2/
- **#2 (Follow remote author):** Same endpoint, but use the remote author's FQID as the foreign_id parameter. Your node also sends the request to the remote author's inbox endpoint. Example: PUT /api/authors/1/following/http%3A%2F%2Fremote.com%2Fapi%2Fauthors%2Fabc%2F

---

### DELETE /api/authors/{author_id}/following/{foreign_id}/

Removes a follow relationship between two authors. This completely severs the connection.

When called, it deletes any existing Follow object and also clears any pending FollowRequest between these two authors. After unfollowing, the target author's posts will no longer appear in your stream.

**Auth:** Required. The authenticated user must be `{author_id}`.

**Pagination:** Not applicable.

**Response:** 200 OK on success

**User Stories:**
- **#5 (Unfollow):** Call this endpoint with the authenticated user's ID and the target author's ID to stop following them. Example: Alice (ID 1) unfollows Bob (ID 2) → DELETE /api/authors/1/following/2/ . Call this when the user clicks "Unfollow" on an author's profile or in their following list.

---

### PUT /api/authors/{author_id}/followers/{foreign_id}/

Accepts a follow request from another author. This is the "approve" action in the follow workflow.

When someone sends you a follow request (visible via the follow_requests endpoint), you call this endpoint to approve it. This creates the actual Follow relationship, allowing the requester to see your posts in their stream.

**Auth:** Required. The authenticated user must be `{author_id}` (the person accepting).

**Pagination:** Not applicable.

**Response Codes:**
- 200: Follow request accepted successfully
- 404: No pending follow request found from this author

**User Stories:**
- **#3 (Approve follower):** After viewing pending requests via GET /follow_requests/, call this endpoint to approve a specific request. Example: Bob (ID 2) accepts Alice's (ID 1) request → PUT /api/authors/2/followers/1/ . This creates the follow relationship and Alice will now see Bob's posts.

---

### DELETE /api/authors/{author_id}/followers/{foreign_id}/

Rejects a pending follow request or removes an existing follower.

If there's a pending request from this author, it rejects it (status becomes "rejected"). If the author is already a follower, this removes them from your followers list.

**Auth:** Required.

**Pagination:** Not applicable.

**Response:** 200 OK on success

**User Stories:**
- **#3 (Deny follower):** After viewing pending requests via GET /follow_requests/, call this endpoint to reject a specific request. Example: Bob (ID 2) rejects Charlie's (ID 3) request → DELETE /api/authors/2/followers/3/ . The request is marked as rejected and no follow relationship is created.

---

### GET /api/authors/{author_id}/follow_requests/

Returns all pending follow requests for an author. These are authors who have requested to follow you but haven't been approved yet.

The response includes the actor (who wants to follow) and object (who they're following - you), along with a summary string describing the request and its status. Each request has status "pending" until approved or rejected.

**Auth:** Required. Only the author can view their own pending requests.

**Pagination:** Supported. Use `page` and `size` query parameters to navigate through multiple pages of requests.

**User Stories:**
- **#4 (See follow requests):** Call this endpoint to display all pending follow requests to the user. Present each request showing who wants to follow you, then provide buttons or links to approve (PUT /followers/{id}/) or reject (DELETE /followers/{id}/) each request. Call this when the user visits their "Follow Requests" page or when displaying a notification badge for pending requests.

---

### POST /api/authors/{author_id}/inbox/

Receives objects from remote nodes. This is the endpoint that other nodes call to send you follow requests.

When a remote author wants to follow you, their node sends a POST request to your inbox endpoint. The request body contains a follow object with the actor (the requester) and object (you). This creates a pending FollowRequest in your system, just like a local follow request.

**Auth:** Accepts both local cookie authentication and remote HTTP Basic Authentication from other nodes.

**Pagination:** Not applicable.

**Response:** 201 Created on success

**User Stories:**
- **#2 (Follow remote author):** When a remote author follows you, their node contacts this endpoint to deliver the follow request. The request then appears in your follow_requests list (story #4). Handle it the same way you handle local requests.
- **#3 (Approve remote follower):** After a remote follow request arrives via this endpoint, approve it using PUT /followers/{id}/ the same way you approve local requests. The remote author's node will be notified of the acceptance.

---

## User Story Implementation Guide

### Story #1: Follow Local Authors
1. Call GET /api/authors/ to retrieve available authors on the node
2. Display these authors to the user so they can choose someone to follow
3. Call PUT /api/authors/{user_id}/following/{target_id}/ with the user's ID and the selected author's ID
4. Display a confirmation message indicating the request was sent

### Story #2: Follow Remote Authors
1. Discover remote authors (from other nodes or the local author list)
2. Call PUT /api/authors/{user_id}/following/{remote_fqid}/ using the remote author's FQID
3. Your node also POSTs the follow request to the remote author's inbox endpoint
4. The request appears in their follow_requests (story #4) for them to approve

### Story #3: Approve or Deny Follow Requests
1. Call GET /api/authors/{user_id}/follow_requests/ to retrieve pending requests
2. Display each request to the user with options to approve or deny
3. To approve: Call PUT /api/authors/{user_id}/followers/{requester_id}/
4. To deny: Call DELETE /api/authors/{user_id}/followers/{requester_id}/

### Story #4: See Follow Requests
1. Call GET /api/authors/{user_id}/follow_requests/
2. Display each pending request showing who wants to follow the user
3. Provide approve/deny buttons that link to the appropriate endpoints

### Story #5: Unfollow Authors
1. Call GET /api/authors/{user_id}/following/ to see who you currently follow
2. Display this list to the user with an unfollow option for each author
3. When user clicks unfollow: Call DELETE /api/authors/{user_id}/following/{target_id}/

---

## Testing Examples

```bash
# Login to get session cookie
curl -c cookies.txt -X POST http://localhost:8000/login/ \
  -d "username=alice&password=test123"

# List all authors on the node
curl http://localhost:8000/api/authors/

# Alice (id=1) sends follow request to Bob (id=2)
curl -b cookies.txt -X PUT http://localhost:8000/api/authors/1/following/2/

# Check Alice's follow requests
curl -b cookies.txt http://localhost:8000/api/authors/1/follow_requests/

# Bob accepts Alice's request
curl -b cookies.txt -X PUT http://localhost:8000/api/authors/2/followers/1/

# Alice unfollows Bob
curl -b cookies.txt -X DELETE http://localhost:8000/api/authors/1/following/2/
```

---

## Response Format Note

This implementation uses `items` as the key for paginated lists rather than specific keys like `followers` or `following` as shown in the spec example. This provides consistency across all list endpoints - the key name stays the same while the `type` field indicates what type of objects are returned. This is a minor deviation from the spec example but improves API consistency.
