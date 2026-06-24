import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create a superuser if none exists, or update password from env vars'

    def handle(self, *args, **kwargs):
        User = get_user_model()

        email    = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not email or not password:
            self.stderr.write(
                'ERROR: Set DJANGO_SUPERUSER_EMAIL and '
                'DJANGO_SUPERUSER_PASSWORD environment variables.'
            )
            return

        user = User.objects.filter(is_superuser=True).first()

        if user:
            # Always sync the password from the env var
            user.set_password(password)
            user.email = email
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Superuser "{email}" password updated.'))
        else:
            create_kwargs = {'email': email, 'password': password}
            if hasattr(User, 'username'):
                username = os.environ.get('DJANGO_SUPERUSER_USERNAME', email.split('@')[0])
                create_kwargs['username'] = username

            User.objects.create_superuser(**create_kwargs)
            self.stdout.write(self.style.SUCCESS(f'Superuser "{email}" created successfully.'))