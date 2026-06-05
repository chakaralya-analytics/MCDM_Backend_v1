from django.db import migrations, models

def set_project_types(apps, schema_editor):
    """Set correct project_type based on existing data"""
    AHPProject = apps.get_model('ahp_api', 'AHPProject')
    
    for project in AHPProject.objects.all():
        # If alternatives exist and are not empty, it's a full analysis
        if project.alternatives and len(project.alternatives) > 0:
            project.project_type = 'full_analysis'
        else:
            project.project_type = 'criteria_only'
        project.save()

def reverse_project_types(apps, schema_editor):
    """Reverse migration - not much to do here"""
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('ahp_api', '0001_initial'),
    ]

    operations = [
        # Add project_type column with temporary default
        migrations.AddField(
            model_name='ahpproject',
            name='project_type',
            field=models.CharField(
                choices=[('criteria_only', 'Criteria Only'), ('full_analysis', 'Full Analysis')],
                default='criteria_only',
                max_length=20
            ),
        ),
        
        # Add timestamps
        migrations.AddField(
            model_name='ahpproject',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='ahpproject',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        
        # Increase project_name length
        migrations.AlterField(
            model_name='ahpproject',
            name='project_name',
            field=models.CharField(max_length=200),
        ),
        
        # Set correct project_type based on existing data
        migrations.RunPython(set_project_types, reverse_project_types),
        
        # NOW make alternative fields nullable (after setting correct types)
        migrations.AlterField(
            model_name='ahpproject',
            name='alternatives',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AlterField(
            model_name='ahpproject',
            name='alternative_matrices',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AlterField(
            model_name='ahpproject',
            name='ranking_data',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AlterField(
            model_name='ahpproject',
            name='ranking_list',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AlterField(
            model_name='ahpproject',
            name='alternative_scores',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]