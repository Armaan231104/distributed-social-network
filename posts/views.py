from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Q
from django.views import View
from .models import Entry, HostedImage
from accounts.models import Author, Follow
from nodes.models import RemoteNode
from interactions.views import user_can_access_entry
import json
from functools import wraps
import requests
from accounts.serializers import AuthorSerializer
from accounts.utils import normalize_fqid
from nodes.utils import find_remote_node_for_url

def get_image_url(entry, request):
    if not entry.image:
        return None
    try:
        url = entry.image.url
        if url.startswith('http'):
            return url  # Cloudinary or remote URL
        return request.build_absolute_uri(url)  # local file
    except (ValueError, AttributeError):
        return None
    
def fetch_remote_author_posts(remote_author):
    print("\n--- ENTER fetch_remote_author_posts ---")
    print("Remote author:", remote_author)

    if remote_author.user:
        print("Remote author is actually local → skipping")
        return Entry.objects.none()

    author_url = normalize_fqid(remote_author.id)
    print("Author URL:", author_url)

    if not author_url or not author_url.startswith("http"):
        print("⚠️ Invalid remote author ID:", author_url)
        return Entry.objects.none()

    node = find_remote_node_for_url(author_url) or find_remote_node_for_url(remote_author.host)
    print("Node found:", node)

    if not node:
        print("No node found → returning empty")
        return Entry.objects.none()

    def _extract_posts(payload):
        if isinstance(payload, list):
            return payload

        if not isinstance(payload, dict):
            return []

        for key in ("src", "items", "entries", "posts"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

        return []

    def _candidate_posts_urls(author_payload, fallback_author_url):
        urls = []

        if isinstance(author_payload, dict):
            for key in ("posts", "entries", "items"):
                value = author_payload.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    urls.append(value.rstrip("/") + "/")

        base = fallback_author_url.rstrip("/")
        urls.extend([
            f"{base}/posts/",
            f"{base}/entries/",
        ])

        seen = set()
        deduped = []
        for url in urls:
            if url not in seen:
                deduped.append(url)
                seen.add(url)

        return deduped

    try:
        print("Fetching remote author object...")
        author_response = requests.get(
            author_url,
            auth=(node.username, node.password),
            timeout=10,
        )

        print("Author response status:", author_response.status_code)

        if author_response.status_code != 200:
            print("Could not fetch remote author → skipping")
            return Entry.objects.none()

        author_data = author_response.json()
        if isinstance(author_data, dict):
            print("Author JSON keys:", author_data.keys())
        else:
            print("Author JSON type:", type(author_data))

        candidate_urls = _candidate_posts_urls(author_data, author_url)
        print("Candidate posts URLs:", candidate_urls)

        posts = []
        posts_url_used = None

        for posts_url in candidate_urls:
            print("Trying posts URL:", posts_url)

            response = requests.get(
                posts_url,
                auth=(node.username, node.password),
                timeout=10,
            )

            print("Posts response status:", response.status_code)

            if response.status_code != 200:
                print("Not usable, trying next URL...")
                continue

            data = response.json()
            if isinstance(data, dict):
                print("Posts JSON keys:", data.keys())
            else:
                print("Posts JSON type:", type(data))

            posts = _extract_posts(data)
            posts_url_used = posts_url
            print("Posts received:", len(posts))
            break

        if posts_url_used is None:
            print("No working posts endpoint found")
            return Entry.objects.none()

        print("Using posts URL:", posts_url_used)

        stored_entries = []

        for i, post in enumerate(posts):
            print(f"\nProcessing post {i}")

            if not isinstance(post, dict):
                print("Skipping non-dict post payload")
                continue

            visibility = post.get("visibility", "PUBLIC")
            if visibility == "DELETED":
                print("Skipping deleted post")
                continue

            fqid = normalize_fqid(post.get("id"))
            if not fqid:
                print("Skipping post without ID")
                continue

            entry, created = Entry.objects.get_or_create(
            fqid=fqid,
            defaults={
                    "title": post.get("title", ""),
                    "content": post.get("content", ""),
                    "content_type": post.get("contentType", "text/plain"),
                    "visibility": visibility,
                    "remote_author": remote_author,
                    "image_url": post.get("image") if isinstance(post.get("image"), str) and (post.get("image", "").startswith("http") or post.get("image", "").startswith("data:")) else None,
                },
            )

            print("Entry:", entry.id, "| Created:", created)

            update_fields = []

            if not created:
                if entry.remote_author_id != remote_author.id:
                    entry.remote_author = remote_author
                    update_fields.append("remote_author")
                if entry.title != post.get("title", ""):
                    entry.title = post.get("title", "")
                    update_fields.append("title")
                if entry.content != post.get("content", ""):
                    entry.content = post.get("content", "")
                    update_fields.append("content")
                if entry.content_type != post.get("contentType", "text/plain"):
                    entry.content_type = post.get("contentType", "text/plain")
                    update_fields.append("content_type")
                if entry.visibility != visibility:
                    entry.visibility = visibility
                    update_fields.append("visibility")
                
                # sync remote image URL

                incoming_image_url = post.get("image")
                if not isinstance(incoming_image_url, str) or not (incoming_image_url.startswith("http") or incoming_image_url.startswith("data:")):
                    incoming_image_url = None
                if entry.image_url != incoming_image_url:
                    entry.image_url = incoming_image_url
                    update_fields.append("image_url")

            if update_fields:
                entry.save(update_fields=list(set(update_fields)))

            stored_entries.append(entry.id) 

        result = Entry.objects.filter(id__in=stored_entries)
        print("Returning stored entries:", result.count())
        print("--- EXIT fetch_remote_author_posts ---\n")
        return result

    except Exception as e:
        print("🔥 ERROR in fetch_remote_author_posts:", str(e))
        raise

def serialize_entry(entry, request=None):
    """Serialize an Entry into the spec-style API shape used for federation."""
    author = entry.get_author
    comments_url = None
    likes_url = None
    if entry.fqid:
        comments_url = f"{entry.fqid.rstrip('/')}/comments"
        likes_url = f"{entry.fqid.rstrip('/')}/likes"

    return {
        "type": "entry",
        "title": entry.title,
        "id": entry.fqid,
        "web": None,
        "description": entry.title,
        "contentType": entry.content_type,
        "content": entry.content,
        "author": AuthorSerializer(author).data if author else None,
        "comments": {
            "type": "comments",
            "id": comments_url,
            "web": None,
            "page_number": 1,
            "size": 5,
            "count": entry.comments.count(),
            "src": [],
        },
        "likes": {
            "type": "likes",
            "id": likes_url,
            "web": None,
            "page_number": 1,
            "size": 50,
            "count": entry.likes.count(),
            "src": [],
        },
        "published": entry.published_at.isoformat() if entry.published_at else None,
        "visibility": entry.visibility,
    }


def get_entries_visible_to_requester(author, request):
    """Return entries visible to the current requester for a given author."""
    qs = Entry.objects.exclude(visibility="DELETED").order_by('-published_at')

    if author.user:
        qs = qs.filter(author=author.user)
    else:
        qs = qs.filter(remote_author=author)

    if not request.user.is_authenticated:
        return qs.filter(visibility="PUBLIC")

    if getattr(request.user, "is_remote_node", False):
        return qs.filter(visibility="PUBLIC")

    try:
        viewer = request.user.author
    except Author.DoesNotExist:
        return qs.filter(visibility="PUBLIC")

    if viewer.id == author.id:
        return qs

    if viewer.is_friend(author):
        return qs.filter(visibility__in=["PUBLIC", "UNLISTED", "FRIENDS"])

    if viewer.is_following(author):
        return qs.filter(visibility__in=["PUBLIC", "UNLISTED"])

    return qs.filter(visibility="PUBLIC")


class AuthorEntriesView(View):
    """GET recent entries for a specific author, using the spec path."""

    def get(self, request, author_id):
        author = get_object_or_404(Author, id=normalize_fqid(author_id))
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 10))

        visible_entries = get_entries_visible_to_requester(author, request)
        total = visible_entries.count()
        start = (page - 1) * size
        end = start + size
        page_entries = visible_entries[start:end]

        return JsonResponse({
            "type": "entries",
            "page_number": page,
            "size": size,
            "count": total,
            "src": [serialize_entry(entry, request=request) for entry in page_entries],
        })
def get_entry_by_id(entry_id):
    entry_id = str(entry_id)

    if entry_id.startswith("http"):
        entry_id = normalize_fqid(entry_id)
        return get_object_or_404(Entry, fqid=entry_id)

    return get_object_or_404(Entry, id=entry_id)
def approved_author_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        try:
            author = request.user.author
        except Author.DoesNotExist:
            return redirect("login")

        if not author.is_approved:
            return redirect("pending-approval")

        return view_func(request, *args, **kwargs)
    return wrapper

def get_stream_entries_for_user(user):
    print("\n=== ENTER get_stream_entries_for_user ===")

    base_qs = Entry.objects.exclude(
        visibility="DELETED"
    ).select_related('author__author')

    print("Base queryset ready")

    if not user.is_authenticated:
        print("User not authenticated")
        result = base_qs.filter(
            visibility="PUBLIC"
        ).order_by('-published_at')
        print("Returning public posts:", result.count())
        return result

    try:
        current_author = user.author
        print("Current author:", current_author)
    except Author.DoesNotExist:
        print("User has no Author object")
        result = base_qs.filter(
            Q(author=user) | Q(visibility="PUBLIC")
        ).order_by('-published_at').distinct()
        print("Fallback posts:", result.count())
        return result

    print("Fetching following relationships...")
    following_qs = Follow.objects.filter(
        follower=current_author,
        followee__user__isnull=False
    ).select_related('followee__user')

    print("Following count:", following_qs.count())

    followed_authors = [f.followee for f in following_qs]
    followed_users = [a.user for a in followed_authors if a.user]

    print("Followed users count:", len(followed_users))

    friend_users = [
        a.user for a in followed_authors
        if a.user and a.is_following(current_author)
    ]

=======
>>>>>>> c90e62147ca3e93f64609ba7bf718241d1e4c1bd
    print("Friend users count:", len(friend_users))

    print("Building local entries query...")
    local_entries = base_qs.filter(
        Q(author=user) |
        Q(visibility="PUBLIC") |
        Q(author__in=followed_users, visibility="UNLISTED") |
        Q(author__in=friend_users, visibility="FRIENDS")
    )

>>>>>>> c90e62147ca3e93f64609ba7bf718241d1e4c1bd
    print("Local entries count:", local_entries.count())

    print("Remote follows count:", remote_following.count())
    
    # Remote friends (mutual follow with remote authors)
    remote_friend_authors = [
        f.followee for f in remote_following
        if Follow.objects.filter(follower=f.followee, followee=current_author).exists()
    ]

    # Add remote friends' FRIENDS entries to query
    if remote_friend_authors:
        remote_friends_entries = base_qs.filter(
            remote_author__in=remote_friend_authors,
            visibility="FRIENDS"
        )
        local_entries = local_entries | remote_friends_entries

    remote_entries = Entry.objects.none()

    for follow in remote_following:
        print("Fetching remote posts for:", follow.followee)
        try:
            posts = fetch_remote_author_posts(follow.followee)
            print("Fetched remote posts:", posts.count())
            remote_entries = remote_entries | posts
        except Exception as e:
            print("ERROR in remote fetch:", e)

    print("Combining local + remote entries...")
    all_entries = local_entries | remote_entries

    final = all_entries.order_by('-published_at').distinct()
    print("Final entries count:", final.count())

    print("=== EXIT get_stream_entries_for_user ===\n")
    return final

@approved_author_required
def stream(request):
    print("\n=== ENTER stream ===")

    import os
    import cloudinary
    import socialdistribution.settings as settings

    print("User:", request.user)
    print("Authenticated:", request.user.is_authenticated)

    print("=== Cloudinary Config Check ===")
    print("CLOUDINARY_CLOUD_NAME :", os.environ.get('CLOUDINARY_CLOUD_NAME'))
    print("CLOUDINARY_API_KEY    :", os.environ.get('CLOUDINARY_API_KEY'))
    print("CLOUDINARY_API_SECRET :", os.environ.get('CLOUDINARY_API_SECRET'))
    print("DEBUG                 :", settings.DEBUG)
    print("DEFAULT_FILE_STORAGE  :", getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET'))
    print("Cloudinary config     :", cloudinary.config().__dict__)

    try:
        posts = get_stream_entries_for_user(request.user)
        print("Posts fetched:", posts.count())
    except Exception as e:
        print("ERROR in get_stream_entries_for_user:", e)
        raise

    current_user_author = request.user.author if request.user.is_authenticated else None
    print("=== EXIT stream ===\n")
    return render(request, 'posts/stream.html', {
        'posts': posts,                                       
        'current_user_author': current_user_author,
    })

def serialize_entry_for_stream(request, entry):
    """
    Converts an entry into JSON format for the stream API.
    """

    image_url = entry.image_url or get_image_url(entry, requests)

    author_obj = None

    author_profile = entry.get_author
    profile_image = None

    if author_profile.profileImage:
        if hasattr(author_profile.profileImage, "url"):
            profile_image = request.build_absolute_uri(author_profile.profileImage.url)
        else:
            profile_image = author_profile.profileImage  # remote URL

    author_obj = {
        "id": author_profile.id,
        "displayName": author_profile.displayName,
        "host": author_profile.host,
        "web": author_profile.web,
        "github": author_profile.github,
        "profileImage": profile_image,
    }

    return {
        "id": entry.fqid,
        "title": entry.title,
        "content": entry.content,
        "contentType": entry.content_type,
        "visibility": entry.visibility,
        "published": entry.published_at.isoformat(),
        "updated": entry.updated_at.isoformat(),
        "isEdited": entry.is_edited,
        "image": image_url,
        "author": author_obj,
    }


def stream_api(request):
    """
    Returns entries that should appear in the user's stream.

    Visibility Rules:
    - Unauthenticated users receive PUBLIC entries only.
    - Authenticated users receive:
        • Their own entries (excluding DELETED)
        • All PUBLIC entries
        • UNLISTED entries from authors they follow
        • FRIENDS entries from mutual followers
    """

    posts = get_stream_entries_for_user(request.user)

    data = [serialize_entry_for_stream(request, post) for post in posts]

    return JsonResponse({
        "type": "entries",
        "count": len(data),
        "src": data,
    })

@login_required
def entry_detail(request, entry_id):
    try:
        print("ENTRY ID:", entry_id)

        entry = get_entry_by_id(entry_id)
        print("ENTRY:", entry)

        print("CHECK ACCESS")
        access = user_can_access_entry(request.user, entry)
        print("ACCESS RESULT:", access)

        if not access:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        print("COMMENTS")
        comments = entry.comments.all()

        print("AUTHOR")
        entry_author = entry.get_author

        author_path = entry_author.id if entry_author else None
        current_user_author = request.user.author if request.user.is_authenticated else None
        return render(request, 'interactions/entry_detail.html', {
            'current_user_author': current_user_author,
            'entry': entry,
            'comments': comments,
            'author_path': author_path,
            'entry_author':entry_author,
        })

    except Exception as e:
        print("ERROR:", str(e))
        raise

def entry_image(request, author_id, entry_id):
    entry = get_entry_by_id(entry_id)

    if not entry.image:
        return JsonResponse({"error": "Not an image"}, status=404)

    from interactions.views import user_can_access_entry
    if not user_can_access_entry(request.user, entry):
        return JsonResponse({"error": "Forbidden"}, status=403)

    return HttpResponse(entry.image.read(), content_type="image/png")

@login_required
def create_entry(request):
    """
    Creates a new entry.

    Supports:
    - JSON requests for text/plain and text/markdown entries
    - multipart uploads for image entries
    """

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    valid_visibilities = [v[0] for v in Entry.VISIBILITY_CHOICES]

    if request.content_type and request.content_type.startswith("multipart/form-data"):

        title = request.POST.get("title", "")
        content = request.POST.get("content", "")
        content_type = request.POST.get("contentType", "image")
        visibility = request.POST.get("visibility", "PUBLIC")

        if visibility not in valid_visibilities:
            return JsonResponse({"error": "Invalid visibility"}, status=400)

        image_file = request.FILES.get("image")

        if not image_file:
            return JsonResponse({"error": "Image file required for image posts"}, status=400)

        entry = Entry.objects.create(
            author=request.user,
            title=title,
            content=content,
            content_type=content_type,
            visibility=visibility,
            image=image_file
        )

        fanout_entry_to_remote_followers(entry, request.user)

        return JsonResponse({"id": entry.fqid}, status=201)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    title = data.get("title", "")
    content = data.get("content", "")
    content_type = data.get("contentType", "text/plain")
    visibility = data.get("visibility", "PUBLIC")

    if content_type not in dict(Entry.CONTENT_TYPES).keys():
        return JsonResponse({"error": "Invalid contentType"}, status=400)

    if visibility not in valid_visibilities:
        return JsonResponse({"error": "Invalid visibility"}, status=400)

    entry = Entry.objects.create(
        author=request.user,
        title=title,
        content=content,
        content_type=content_type,
        visibility=visibility
    )

    fanout_entry_to_remote_followers(entry, request.user)

    return JsonResponse({"id": entry.fqid}, status=201)

@require_http_methods(["GET", "PATCH", "DELETE"])
def entry_detail_api(request, entry_id):
    """
    Handles GET (read), PATCH (partial update), and DELETE for a single entry.
    
    - GET: Returns a JSON representation of an entry.
    - PATCH: Partially updates an entry (only author).
    - DELETE: Soft deletes an entry (only author).
    """
    entry = get_entry_by_id(entry_id)
    
    # GET - Read entry
    if request.method == "GET":
        if entry.visibility == "DELETED":
            if not request.user.is_authenticated or not request.user.is_staff:
                return JsonResponse({"error": "Not found"}, status=404)
    entry = get_entry_by_id(entry_id)
    
    # GET - Read entry
    if request.method == "GET":
        if entry.visibility == "DELETED":
            if not request.user.is_authenticated or not request.user.is_staff:
                return JsonResponse({"error": "Not found"}, status=404)

        if entry.visibility in ["PUBLIC", "UNLISTED"]:
            pass
        elif entry.visibility == "FRIENDS":
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Forbidden"}, status=403)
            if request.user != entry.author:
                try:
                    viewer_author = request.user.author
                    entry_author = entry.author.author
                except Author.DoesNotExist:
                    return JsonResponse({"error": "Forbidden"}, status=403)
                if not viewer_author.is_friend(entry_author):
                    return JsonResponse({"error": "Forbidden"}, status=403)
        if entry.visibility in ["PUBLIC", "UNLISTED"]:
            pass
        elif entry.visibility == "FRIENDS":
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Forbidden"}, status=403)
            if request.user != entry.author:
                try:
                    viewer_author = request.user.author
                    entry_author = entry.author.author
                except Author.DoesNotExist:
                    return JsonResponse({"error": "Forbidden"}, status=403)
                if not viewer_author.is_friend(entry_author):
                    return JsonResponse({"error": "Forbidden"}, status=403)

        image_url = entry.image_url or get_image_url(entry, request)
    

        return JsonResponse({
            "id": entry.fqid,
            "title": entry.title,
            "content": entry.content,
            "contentType": entry.content_type,
            "visibility": entry.visibility,
            "published": entry.published_at.isoformat(),
            "image": image_url,
        })
    
    # PATCH - Partial update (only author)
    if request.method == "PATCH":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        if entry.author != request.user:
            return HttpResponseForbidden()
        
        if entry.visibility == "DELETED":
            return JsonResponse({"error": "Entry not found"}, status=404)
        
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if "content" in data:
            entry.content = data["content"].strip()
        
        if "title" in data:
            entry.title = data["title"]
        
        entry.save()

        return JsonResponse({
            "id": entry.fqid,
            "message": "Updated successfully",
            "content": entry.content
        }, status=200)
    
    # DELETE - Soft delete (only author)
    if request.method == "DELETE":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        if entry.author != request.user:
            return HttpResponseForbidden()
        
        entry.soft_delete()

        fanout_entry_to_remote_followers(entry, request.user)
        
        return JsonResponse({"deleted": True})
    
    # PATCH - Partial update (only author)
    if request.method == "PATCH":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        if entry.author != request.user:
            return HttpResponseForbidden()
        
        if entry.visibility == "DELETED":
            return JsonResponse({"error": "Entry not found"}, status=404)
        
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if "content" in data:
            entry.content = data["content"].strip()
        
        if "title" in data:
            entry.title = data["title"]
        
        entry.save()

        return JsonResponse({
            "id": entry.fqid,
            "message": "Updated successfully",
            "content": entry.content
        }, status=200)
    
    # DELETE - Soft delete (only author)
    if request.method == "DELETE":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        if entry.author != request.user:
            return HttpResponseForbidden()
        
        entry.soft_delete()

        fanout_entry_to_remote_followers(entry, request.user)
        
        return JsonResponse({"deleted": True})


@login_required
def upload_hosted_image(request):
    """
    Uploads an image hosted by this node.
    """

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse({"error": "Image file required"}, status=400)

    hosted_image = HostedImage.objects.create(
        author=request.user,
        image=image_file
    )

    image_url = request.build_absolute_uri(hosted_image.image.url)

    return JsonResponse({
        "id": str(hosted_image.id),
        "url": image_url
    }, status=201)


@login_required
def my_entries(request):
    """
    Returns all non-deleted entries created by the user.
    """

    entries = Entry.objects.filter(
        author=request.user
    ).exclude(
        visibility="DELETED"
    )

    def entry_to_dict(e):

        image_url = e.image_url or get_image_url(e, request)
        return {
            "id": e.fqid,
            "title": e.title,
            "content": e.content,
            "contentType": getattr(e, "content_type", "text/plain"),
            "image": image_url,
            "visibility": e.visibility,
            "published": e.published_at.isoformat(),
        }

    data = [entry_to_dict(e) for e in entries]

    return JsonResponse(data, safe=False)


@login_required
def edit_entry(request, entry_id):
    """
    Updates an existing entry.

    Only the author may edit.
    Deleted entries cannot be edited.
    """

    entry = get_entry_by_id(entry_id)
    entry = get_entry_by_id(entry_id)

    if entry.author != request.user:
        return HttpResponseForbidden()

    if entry.visibility == "DELETED":
        return JsonResponse({"error": "Entry not found"}, status=404)

    if request.method != "PUT":
        return JsonResponse({"error": "PUT required"}, status=400)

    # A multipart/form-data => editing image/caption/title, optionally replace image
    if request.content_type and request.content_type.startswith("multipart/form-data"):

        entry.title = request.POST.get("title", entry.title)
        entry.content = request.POST.get("content", entry.content)

        ct = request.POST.get("contentType", getattr(entry, "content_type", "text/plain"))

        if ct not in dict(Entry.CONTENT_TYPES).keys():
            return JsonResponse({"error": "Invalid contentType"}, status=400)

        entry.content_type = ct

        new_image = request.FILES.get("image")

        if new_image:
            entry.image = new_image

        entry.save()

        return JsonResponse({"updated": True}, status=200)
    
    # B JSON => editing title/content/contentType for text posts
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "title" in data:
        entry.title = data["title"]

    if "content" in data:
        entry.content = data["content"]

    if "contentType" in data:

        ct = data["contentType"]

        if ct not in dict(Entry.CONTENT_TYPES).keys():
            return JsonResponse({"error": "Invalid contentType"}, status=400)

        entry.content_type = ct

    entry.save()

    fanout_entry_to_remote_followers(entry, request.user)

    fanout_entry_to_remote_followers(entry, request.user)

    return JsonResponse({"updated": True}, status=200)

@approved_author_required
@approved_author_required
@login_required
@require_POST
def delete_entry_ui(request, entry_id):
    """
    Soft deletes an entry via the UI.

    Only the author may delete.
    """

    entry = get_entry_by_id(entry_id)
    entry = get_entry_by_id(entry_id)

    if entry.author != request.user:
        return HttpResponseForbidden("You cannot delete this entry.")

    entry.soft_delete()

    fanout_entry_to_remote_followers(entry, request.user)

    fanout_entry_to_remote_followers(entry, request.user)

    referrer = request.META.get("HTTP_REFERER")

    if referrer:
        return redirect(referrer)
    else:
        return redirect("stream")


@login_required
def deleted_entries(request):
    """
    Node admin view: lists all soft-deleted entries across all authors.

    Access Control:
    - Must be authenticated (enforced by @login_required → redirects to login).
    - Must be staff (is_staff=True); non-staff receive 403 Forbidden.

    Behaviour:
    - Entries are never hard-deleted; soft_delete() sets visibility to "DELETED".
    - This view is the only place in the UI where DELETED entries are visible.
    - Results are ordered by updated_at descending (most recently deleted first).
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()

    entries = Entry.objects.filter(visibility="DELETED").select_related('author__author').order_by('-updated_at')
    return render(request, 'posts/deleted_entries.html', {'entries': entries})


# ----- REMOTE API ----- #


def send_entry_to_inbox(entry, author, inbox_url, node):
    """Send a spec-compliant entry object to a remote inbox."""
    payload = {
        "type": "entry",
        "id": entry.fqid,
        "title": entry.title,
        "content": entry.content,
        "contentType": entry.content_type,
        "visibility": entry.visibility,
        "published": entry.published_at.isoformat(),
        "author": {
            "type": "author",
            "id": author.id,
            "displayName": author.displayName,
            "host": author.host,
            "github": author.github or None,
            "profileImage": author.profileImage.url if author.profileImage else None,
            "web": author.web or None,
        }
    }
    try:
        requests.post(
            inbox_url,
            json=payload,
            auth=(node.username, node.password),
            timeout=5
        )
    except requests.RequestException as e:
        print("Fanout failed:", e)
def fanout_entry_to_remote_followers(entry, user):
    """Send entry to all remote followers' inboxes."""
    try:
        author = user.author
    except Author.DoesNotExist:
        return

    # get all followers who are remote (no local user account)
    remote_followers = Follow.objects.filter(
        followee=author,
        follower__user__isnull=True  # remote authors have no local user
    ).select_related('follower')

    for follow in remote_followers:
        remote_author = follow.follower

        # find which node this remote author belongs to
        remote_host = remote_author.host.rstrip('/')
        node = next((n for n in RemoteNode.objects.filter(is_active=True) if remote_host.startswith(n.url.rstrip('/'))), None)
        if not node:
            continue

        inbox_url = f"{remote_author.id.rstrip('/')}/inbox/"
        send_entry_to_inbox(entry, author, inbox_url, node)
