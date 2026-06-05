from django.db import migrations, models

def make_emails_unique(apps, schema_editor):
    """
    Add placeholder unique emails for existing users without empty emails
    """
    User = apps.get_model('auth', 'User')
    # Direct database update to avoid signal handlers
    for index, user in enumerate(User.objects.filter(email='')):
        email = f"user_{user.id}_{index}@placeholder.com"
        User.objects.filter(id=user.id).update(email=email)


# custom operation that updates migration state for auth.User only
class AlterAuthUserEmail(migrations.AlterField):
    def state_forwards(self, app_label, state):
        # apply state change under the auth app label
        super().state_forwards('auth', state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # DB change handled separately via RunSQL
        return

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        return

    def describe(self):
        return "Alter auth.User.email field to unique in migration state"

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial_with_phone'),
    ]

    operations = [
        # First add placeholder emails
        migrations.RunPython(make_emails_unique),
        # Add unique index on auth_user table
        migrations.RunSQL(
            "CREATE UNIQUE INDEX unique_email ON auth_user(email);",
            "DROP INDEX unique_email;",
        ),

        # Update migration state for auth.User.email
        AlterAuthUserEmail(
            model_name='user',
            name='email',
            field=models.EmailField(unique=True, max_length=254),
        ),
        
    ]