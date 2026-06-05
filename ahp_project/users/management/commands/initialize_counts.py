from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserProfile
from ahp_api.models import AHPProject

class Command(BaseCommand):
    help = 'Initialize project and alternative counts for all users'

    def handle(self, *args, **options):
        users = User.objects.all()
        updated_count = 0
        
        for user in users:
            try:
                # First ensure user has a profile
                try:
                    profile = user.profile
                except User.profile.RelatedObjectDoesNotExist:
                    profile = UserProfile.objects.create(
                        user=user,
                        max_projects=2,
                        phone_number="Not provided",
                        max_alternatives=5
                    )
                    self.stdout.write(f"Created profile for user {user.username}")
                
                # Count projects
                projects = AHPProject.objects.filter(user=user)
                project_count = projects.count()
                
                # Count alternatives across all projects
                total_alternative_count = 0
                for project in projects:
                    if project.alternatives:
                        total_alternative_count += len(project.alternatives)
                
                # Update profile
                profile.project_count = project_count
                profile.total_alternative_count = total_alternative_count
                profile.save()
                
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated {user.username}: {project_count} projects, {total_alternative_count} alternatives'
                    )
                )
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error updating user {user.username}: {str(e)}'))
                
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} user profiles'))        # Apply the migration (if not already applied)