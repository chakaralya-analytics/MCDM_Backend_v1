"""
Migration 0006 — Phase 2 architecture normalization.

Changes:
1. Create AlternativeCalculation model (relational replacement for the
   timestamp-keyed alternative_matrices JSON blob).
2. Remove the per-project alternative_limit field (limit now comes from
   settings.DEFAULT_ALTERNATIVE_LIMIT so it can be configured per-env
   and later driven by subscription plans).
3. Add DB indexes on AHPProject.user and AHPProject.created_at.
4. Data migration: convert existing alternative_matrices JSON blobs into
   AlternativeCalculation rows so no history is lost.
"""

import datetime
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def migrate_alternative_matrices(apps, schema_editor):
    """Copy JSON-blob history into the new AlternativeCalculation table."""
    AHPProject = apps.get_model('ahp_api', 'AHPProject')
    AlternativeCalculation = apps.get_model('ahp_api', 'AlternativeCalculation')

    migrated_projects = 0
    migrated_rows = 0
    skipped = 0

    for project in AHPProject.objects.exclude(alternative_matrices__isnull=True):
        matrices = project.alternative_matrices
        if not isinstance(matrices, dict) or not matrices:
            continue

        for ts_key, calc_data in matrices.items():
            if not isinstance(calc_data, dict):
                skipped += 1
                continue

            # Try to parse the ISO timestamp key as created_at.
            created_at = django.utils.timezone.now()
            try:
                created_at = datetime.datetime.fromisoformat(ts_key)
                # Make timezone-aware if it isn't already.
                if created_at.tzinfo is None:
                    created_at = django.utils.timezone.make_aware(
                        created_at, datetime.timezone.utc
                    )
            except (ValueError, TypeError):
                pass  # Use now() as fallback

            AlternativeCalculation.objects.create(
                project=project,
                alternatives=calc_data.get('alternatives', []),
                scores=calc_data.get('scores', {}),
                ranking=calc_data.get('ranking', []),
                final_scores=calc_data.get('final_scores', {}),
                created_at=created_at,
            )
            migrated_rows += 1

        migrated_projects += 1

    print(
        f"\n  [0006] Migrated {migrated_rows} alternative calculations "
        f"from {migrated_projects} projects. "
        f"Skipped {skipped} malformed entries."
    )


def reverse_migrate_alternative_matrices(apps, schema_editor):
    """Delete AlternativeCalculation rows (JSON blobs remain untouched)."""
    AlternativeCalculation = apps.get_model('ahp_api', 'AlternativeCalculation')
    AlternativeCalculation.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ahp_api', '0005_ahpproject_alternative_count_and_more'),
    ]

    operations = [
        # 1. Create the AlternativeCalculation table.
        migrations.CreateModel(
            name='AlternativeCalculation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alternatives', models.JSONField()),
                ('scores', models.JSONField()),
                ('ranking', models.JSONField()),
                ('final_scores', models.JSONField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alternative_calculations',
                    to='ahp_api.ahpproject',
                )),
            ],
            options={
                'db_table': 'ahp_api_alternativecalculation',
                'ordering': ['-created_at'],
            },
        ),

        # 2. Add indexes on the new table.
        migrations.AddIndex(
            model_name='alternativecalculation',
            index=models.Index(fields=['project'], name='altcalc_project_idx'),
        ),
        migrations.AddIndex(
            model_name='alternativecalculation',
            index=models.Index(fields=['created_at'], name='altcalc_created_idx'),
        ),

        # 3. Remove alternative_limit — limits live in settings / plans now.
        migrations.RemoveField(
            model_name='ahpproject',
            name='alternative_limit',
        ),

        # 4. Add indexes on AHPProject.
        migrations.AddIndex(
            model_name='ahpproject',
            index=models.Index(fields=['user'], name='ahpproject_user_idx'),
        ),
        migrations.AddIndex(
            model_name='ahpproject',
            index=models.Index(fields=['created_at'], name='ahpproject_created_idx'),
        ),

        # 5. Data migration — convert existing JSON blobs.
        migrations.RunPython(
            migrate_alternative_matrices,
            reverse_code=reverse_migrate_alternative_matrices,
        ),
    ]
