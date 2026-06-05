from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserProfile

class Command(BaseCommand):
    help = 'Create UserProfile objects for users that do not have them'

    def handle(self, *args, **options):
        users_without_profiles = 0
        users_with_profiles = 0
        
        for user in User.objects.all():
            try:
                # Try to access profile
                profile = user.profile
                users_with_profiles += 1
                self.stdout.write(f"User {user.username} already has a profile")
            except User.profile.RelatedObjectDoesNotExist:
                # Create profile if it doesn't exist
                profile = UserProfile.objects.create(
                    user=user,
                    max_projects=2,
                    phone_number="Not provided",
                    max_alternatives=5,
                    project_count=0,
                    total_alternative_count=0
                )
                users_without_profiles += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created profile for user {user.username}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {users_without_profiles} profiles. {users_with_profiles} users already had profiles."
            )
        )