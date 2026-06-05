#\ahp_project\users\migrations\0003_add_phone_numbers.py
from django.db import migrations

def add_phone_numbers(apps, schema_editor):
    """
    Add default phone numbers for existing users
    """
    UserProfile = apps.get_model('users', 'UserProfile')
    
    # Update all existing profiles with a placeholder phone number
    for profile in UserProfile.objects.filter(phone_number__isnull=True):
        profile.phone_number = f"Placeholder-{profile.user_id}"
        profile.save()

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_email_unique'),  # This matches your actual migration history
    ]

    operations = [
        migrations.RunPython(add_phone_numbers),
    ]