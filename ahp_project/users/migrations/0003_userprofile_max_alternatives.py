from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0002_user_email_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='max_alternatives',
            field=models.IntegerField(default=5, help_text='Maximum number of alternatives per project'),
        ),
    ]