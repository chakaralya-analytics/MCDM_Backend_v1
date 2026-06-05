from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),  # Make sure this matches your first migration
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(
                default='Not provided', 
                max_length=15, 
                help_text="User's contact phone number"
            ),
        ),
    ]