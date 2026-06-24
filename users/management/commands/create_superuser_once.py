import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create a superuser if none exists (reads credentials from env vars)'

    def handle(self, *args, **kwargs):
        User = get_user_model()

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('Superuser already exists. Skipping.')
            return

        email    = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not email or not password:
            self.stderr.write(
                'ERROR: Set DJANGO_SUPERUSER_EMAIL and '
                'DJANGO_SUPERUSER_PASSWORD environment variables before running this command.'
            )
            return

        # Build kwargs dynamically — handles both default User (username required)
        # and custom email-only User models
        create_kwargs = {'email': email, 'password': password}
        if hasattr(User, 'username'):
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME', email.split('@')[0])
            create_kwargs['username'] = username

        User.objects.create_superuser(**create_kwargs)
        self.stdout.write(self.style.SUCCESS(f'Superuser "{email}" created successfully.'))