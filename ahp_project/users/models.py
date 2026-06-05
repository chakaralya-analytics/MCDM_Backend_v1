from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Limit sourced from settings.DEFAULT_MAX_PROJECTS so ops can adjust it
    # without touching code.  Phase 3: replace with subscription plan FK.
    max_projects = models.IntegerField(
        default=settings.DEFAULT_MAX_PROJECTS,
        help_text="Maximum number of projects this user can create",
    )
    phone_number = models.CharField(max_length=15, default="Not provided", help_text="User's contact phone number")
    
    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def project_count(self):
        """Returns the current number of projects for this user"""
        return self.user.ahpproject_set.count()
    
    @property
    def can_create_project(self):
        """Check if user can create more projects"""
        return self.project_count < self.max_projects

# Keep your existing signal handlers
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        # Check if profile exists by direct query instead of attribute access
        if not UserProfile.objects.filter(user=instance).exists():
            UserProfile.objects.create(user=instance)
        else:
            instance.profile.save()
    except Exception as e:
        # Create profile if any error occurs
        try:
            UserProfile.objects.create(user=instance)
        except Exception:
            pass  # Fail silently if we can't create the profile during migration
