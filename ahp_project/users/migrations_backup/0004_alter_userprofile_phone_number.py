from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_add_phone_numbers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(default='Not provided', help_text="User's contact phone number", max_length=15),
        ),
    ]