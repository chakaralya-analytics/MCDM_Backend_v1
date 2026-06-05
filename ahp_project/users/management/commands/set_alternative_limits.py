from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserProfile

class Command(BaseCommand):
    help = 'Set alternative limits for existing users'

    def add_arguments(self, parser):
        parser.add_argument('--default', type=int, default=5, 
                            help='Default alternative limit')
        parser.add_argument('--username', type=str, 
                            help='Set limit for specific username')
        parser.add_argument('--limit', type=int, 
                            help='Alternative limit for specific user')

    def handle(self, *args, **options):
        default_limit = options['default']
        specific_username = options.get('username')
        specific_limit = options.get('limit')
        
        if specific_username and specific_limit:
            # Set limit for specific user
            try:
                user = User.objects.get(username=specific_username)
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile.max_alternatives = specific_limit
                profile.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Set alternative limit for {specific_username} to {specific_limit}'
                ))
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User {specific_username} not found'))
        else:
            # Set default limit for all users
            profiles_updated = 0
            for profile in UserProfile.objects.all():
                profile.max_alternatives = default_limit
                profile.save()
                profiles_updated += 1
                
            self.stdout.write(self.style.SUCCESS(
                f'Set alternative limit to {default_limit} for {profiles_updated} users'
            ))