import random
import os
import django





def run():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'socialdistribution.settings')
    django.setup()

    from django.contrib.auth.models import User
    from posts.models import Entry
    from interactions.models import Comment, Like
    from accounts.models import Follow

    print("Cleaning database...")

    Like.objects.all().delete()
    Comment.objects.all().delete()
    Entry.objects.all().delete()
    Follow.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete()

    users = []
    authors = []

    print("Creating 50 users...")

    # Create 50 users
    for i in range(50):
        user = User.objects.create_user(
            username=f"user{i}",
            password="password123"
        )
        users.append(user)
        authors.append(user.author)

    print("Users created")

    # USER0 FOLLOWS EVERYONE
    print("Creating user0 follows...")

    user0 = users[0]
    author0 = user0.author

    for user in users[1:]:
        Follow.objects.get_or_create(
            follower=author0,
            followee=user.author
        )

    print("user0 now follows everyone")

    print("Creating random follows...")

    # Random follow network
    for _ in range(200):
        a1 = random.choice(authors)
        a2 = random.choice(authors)

        if a1 != a2:
            Follow.objects.get_or_create(
                follower=a1,
                followee=a2
            )

    print("Follows created")

    posts = []

    print("Creating posts...")

    # 2 posts per user → 100 posts
    for user in users:
        for i in range(2):
            post = Entry.objects.create(
                author=user,
                title=f"{user.username} post {i}",
                content=f"This is post {i} by {user.username}",
                visibility="PUBLIC"
            )

            posts.append(post)

    print("Posts created")

    comments = []

    print("Creating comments...")

    # 150 comments
    for _ in range(150):
        post = random.choice(posts)
        author = random.choice(authors)

        comment = Comment.objects.create(
            entry=post,
            author=author,
            content="Random seeded comment"
        )

        comments.append(comment)

    print("Comments created")

    print("Creating likes on posts...")

    # 120 post likes
    for _ in range(120):
        post = random.choice(posts)
        author = random.choice(authors)

        Like.objects.get_or_create(
            author=author,
            entry=post,
            comment=None
        )

    print("Post likes created")

    print("Creating likes on comments...")

    # 120 comment likes
    for _ in range(120):
        comment = random.choice(comments)
        author = random.choice(authors)

        Like.objects.get_or_create(
            author=author,
            comment=comment,
            entry=None
        )

    print("Comment likes created")

    print("Database seeded successfully")