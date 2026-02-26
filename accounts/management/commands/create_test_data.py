from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Author, FollowRequest, Follow


class Command(BaseCommand):
    help = 'Creates test data for the follow system'

    def handle(self, *args, **options):
        # Create test users with authors
        test_users = [
            {'username': 'alice', 'first_name': 'Alice', 'last_name': 'Smith', 'password': 'test123'},
            {'username': 'bob', 'first_name': 'Bob', 'last_name': 'Jones', 'password': 'test123'},
            {'username': 'charlie', 'first_name': 'Charlie', 'last_name': 'Brown', 'password': 'test123'},
            {'username': 'diana', 'first_name': 'Diana', 'last_name': 'Prince', 'password': 'test123'},
            {'username': 'eve', 'first_name': 'Eve', 'last_name': 'Wilson', 'password': 'test123'},
        ]

        created_users = []
        for user_data in test_users:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                }
            )
            if created:
                user.set_password(user_data['password'])
                user.save()
                self.stdout.write(f'Created user: {user.username}')
            else:
                self.stdout.write(f'User already exists: {user.username}')
            created_users.append(user)

        # Create some follow relationships
        # Alice follows Bob
        alice = Author.objects.get(user=created_users[0])
        bob = Author.objects.get(user=created_users[1])
        
        if not alice.is_following(bob):
            Follow.objects.create(follower=alice, followee=bob)
            FollowRequest.objects.create(
                actor=alice,
                object=bob,
                summary='Alice wants to follow Bob',
                status=FollowRequest.Status.ACCEPTED
            )
            self.stdout.write('Alice now follows Bob')

        # Charlie follows Alice
        charlie = Author.objects.get(user=created_users[2])
        if not charlie.is_following(alice):
            Follow.objects.create(follower=charlie, followee=alice)
            FollowRequest.objects.create(
                actor=charlie,
                object=alice,
                summary='Charlie wants to follow Alice',
                status=FollowRequest.Status.ACCEPTED
            )
            self.stdout.write('Charlie now follows Alice')

        # Diana follows Alice (pending request)
        diana = Author.objects.get(user=created_users[3])
        if not diana.is_following(alice):
            FollowRequest.objects.get_or_create(
                actor=diana,
                object=alice,
                defaults={
                    'summary': 'Diana wants to follow Alice',
                    'status': FollowRequest.Status.PENDING
                }
            )
            self.stdout.write('Diana sent follow request to Alice')

        # Create a remote author for testing
        remote_author, created = Author.objects.get_or_create(
            id='http://remote-node.example.com/api/authors/remote1/',
            defaults={
                'host': 'http://remote-node.example.com/api/',
                'displayName': 'Remote Author',
                'is_approved': True,
            }
        )
        if created:
            self.stdout.write('Created remote author')

        self.stdout.write(self.style.SUCCESS('\nTest data created successfully!'))
        self.stdout.write('\nLogin credentials:')
        for user_data in test_users:
            self.stdout.write(f'  Username: {user_data["username"]}, Password: {user_data["password"]}')
