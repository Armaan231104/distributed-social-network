# User Stories

document all of the user stories here: where are the endpoints documented, how do they work, why is the user story complete if it's one that doesn't have any functionality

DB Indexing:
- entry.visibility - accessed all the time in stream
- entry.published_at - accessed all the time in stream
- author.host - accessed

## As an author, I want my stream page to be sorted with the most recent entries first (Complete)

**Endpoints Involved**

UI: `GET /posts/stream/`
API: `GET /posts/api/entries/stream/`

**How it works**

Both endpoints delegate to `get_stream_entries_for_user(user)` in `posts/views.py`. This function builds a queryset of entries and always appends `.order_by('-published_at')` before returning, regardless of the user's authentication status:

- Unauthenticated users: `filter(visibility="PUBLIC").order_by('-published_at')`
- Authenticated users (no Author profile): `filter(...).order_by('-published_at').distinct()`
- Authenticated authors: `filter(own | PUBLIC | UNLISTED-from-followed | FRIENDS-from-mutual).order_by('-published_at').distinct()`

The `published_at` field is set once at creation time and never updated on edits, so the sort order reflects when an entry was originally posted. The `published_at` column is indexed (see DB Indexing at the top of this file) to keep stream queries fast as the table grows.

The UI stream page (`posts/stream.html`) renders entries in the order returned by the queryset — newest first. The API endpoint wraps the same ordered queryset into a JSON response with `type`, `count`, and `src` fields, preserving the same order.

**Why it is complete**

Ordering is applied unconditionally inside `get_stream_entries_for_user`, so every path through both the UI and API stream endpoints returns entries sorted newest-first. No additional client-side sorting is required or performed.

## As a node admin, I don't want arrays to be stored in database fields, so that my node won't get slower over time. (Complete)

This has been implemented throughout the codebase. All collection-like data uses separate relational tables with ForeignKey relationships instead of array or JSON columns. No `JSONField` or `ArrayField` is used anywhere in the project.

**How each "array" is stored:**

| Data | Model/Table | Key Fields |
|------|-------------|------------|
| Followers/Following | `Follow` (`accounts/models.py`) | `follower` FK, `followee` FK |
| Follow requests | `FollowRequest` (`accounts/models.py`) | `actor` FK, `object` FK, `status` |
| Likes | `Like` (`interactions/models.py`) | `author` FK, `entry` FK or `comment` FK |
| Comments | `Comment` (`interactions/models.py`) | `author` FK, `entry` FK |
| Posts | `Entry` (`posts/models.py`) | `author` FK |
| Hosted images | `HostedImage` (`posts/models.py`) | `author` FK |

Each item that would conceptually belong to a list is stored as its own row with a ForeignKey back to its parent. Arrays are constructed at request time by querying the related table (e.g. `entry.likes.all()`, `author.followers.all()`). Duplicate-prevention is enforced via `unique_together` and `UniqueConstraint` on the relevant models rather than deduplicating in application code.

Friends (mutual followers) are not stored at all — they are computed at query time as the intersection of the `following` and `followers` querysets in `Author.get_friends()` (`accounts/models.py`).
