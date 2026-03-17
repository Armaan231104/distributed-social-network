import requests
from collections import defaultdict
from accounts.models import Author
from posts.models import Entry


def sync_github_activity():

    # Get authors with GitHub accounts
    authors = Author.objects.exclude(github__isnull=True).exclude(github="")

    # Group authors by GitHub username
    github_groups = defaultdict(list)

    for author in authors:
        if not author.user:
            continue

        username = author.github.rstrip("/").split("/")[-1]
        github_groups[username].append(author)

    # Fetch events once per GitHub user
    for username, authors_with_same_github in github_groups.items():

        url = f"https://api.github.com/users/{username}/events/public"

        print(f"\nFetching events for GitHub user: {username}")

        r = requests.get(url)

        if r.status_code != 200:
            print("Failed to fetch events")
            continue

        events = r.json()

        print("Events returned:", len(events))

        for event in events:

            print("Event type:", event["type"])

            if event["type"] != "PushEvent":
                print("Skipping non-push event")
                continue

            repo = event["repo"]["name"]

            payload = event.get("payload", {})
            commits = payload.get("commits", [])

            if commits:
                commit_messages = "\n".join([c["message"] for c in commits])
                content = f"{commit_messages}\n\nhttps://github.com/{repo}"
            else:
                print("Push event without commits")
                content = f"New push activity on GitHub\n\n<a href='https://github.com/{repo}' target='_blank'>Click me! <i class='fa-brands fa-github'></i></a>"

            # Create entry for each author linked to this GitHub
            for author in authors_with_same_github:

                if Entry.objects.filter(
                    github_event_id=event["id"],
                    author=author.user
                ).exists():
                    print("Entry already exists for:", author.displayName)
                    continue

                print("Creating entry for:", author.displayName)

                Entry.objects.create(
                    author=author.user,
                    title=f"Pushed to {repo}",
                    content=content,
                    visibility="PUBLIC",
                    content_type="text/markdown",
                    github_event_id=event["id"]
                )

    print("\nGitHub sync complete")