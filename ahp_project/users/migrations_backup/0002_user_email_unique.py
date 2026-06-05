from django.db import migrations, models

def make_emails_unique(apps, schema_editor):
    """
    Add placeholder unique emails for existing users without emails
    """
    User = apps.get_model('auth', 'User')
    # Fix: Don't use signal handlers or profile in migrations
    for index, user in enumerate(User.objects.filter(email='')):
        user.email = f"user_{user.id}_{index}@placeholder.com"
        # Use direct update instead of save() to avoid triggering signals
        User.objects.filter(id=user.id).update(email=user.email)

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_add_phone_number'),  # Updated dependency
    ]

    operations = [
        # First add placeholder emails
        migrations.RunPython(make_emails_unique),
        
        # Then make the field unique
        migrations.RunSQL(
            "ALTER TABLE auth_user ADD CONSTRAINT unique_email UNIQUE (email);",
            "ALTER TABLE auth_user DROP CONSTRAINT unique_email;"
        ),
    ]