from django.db import migrations, models
from django.utils import timezone

class Migration(migrations.Migration):
    dependencies = [
        ('ahp_api', '0002_update_ahpproject_table'),
    ]

    operations = [
        # Remove the problematic timestamp fields
        migrations.RemoveField(
            model_name='ahpproject',
            name='created_at',
        ),
        migrations.RemoveField(
            model_name='ahpproject',
            name='updated_at',
        ),
        
        # Add them back with proper defaults
        migrations.AddField(
            model_name='ahpproject',
            name='created_at',
            field=models.DateTimeField(default=timezone.now),
        ),
        migrations.AddField(
            model_name='ahpproject',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]