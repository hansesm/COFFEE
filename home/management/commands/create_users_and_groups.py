from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    help = "Create a superuser, a group, and a normal user"

    def handle(self, *args, **kwargs):
        # Create Superuser
        if not User.objects.filter(username="hansesm").exists():
            User.objects.create_superuser(
                "admin", "admin@example.com", "reverence-referee-lunchbox"
            )
            self.stdout.write(
                self.style.SUCCESS('Superuser "admin" created successfully.')
            )
        else:
            self.stdout.write(self.style.WARNING('Superuser "admin" already exists.'))

        # Create Manager Group
        manager_group, created = Group.objects.get_or_create(name="manager")
        if created:
            self.stdout.write(
                self.style.SUCCESS('Group "manager" created successfully.')
            )
        else:
            self.stdout.write(self.style.WARNING('Group "manager" already exists.'))

        # Create Normal User
        if not User.objects.filter(username="manager").exists():
            user = User.objects.create_user(
                "manager", "user@example.com", "expediter-saline-untapped"
            )
            self.stdout.write(
                self.style.SUCCESS('Normal user "manager" created successfully.')
            )

            # Add the user to the Manager group
            user.groups.add(manager_group)
            self.stdout.write(
                self.style.SUCCESS('User "manager" added to "Manager" group.')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Normal user "manager" already exists.')
            )
