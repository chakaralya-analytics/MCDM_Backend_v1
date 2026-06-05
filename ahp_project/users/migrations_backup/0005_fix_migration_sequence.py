from django.db import migrations

class Migration(migrations.Migration):
    """
    This migration is a no-op that fixes the migration sequence.
    The phone_number field is already in the model, but was added
    without a proper migration. This ensures future migrations work correctly.
    """
    dependencies = [
        ('users', '0004_alter_userprofile_phone_number'),
    ]

    operations = [
        # No operations, just fixes migration sequence
    ]