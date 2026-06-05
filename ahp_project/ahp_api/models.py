# ahp_api/models.py

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AHPProject(models.Model):
    PROJECT_TYPES = [
        ('criteria_only', 'Criteria Only'),
        ('full_analysis', 'Full Analysis')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project_name = models.CharField(max_length=200)
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES, default='criteria_only')

    # Criteria data (always present)
    criteria = models.JSONField()
    pairwise_matrix = models.JSONField()
    weights = models.JSONField()
    consistency_ratio = models.FloatField()

    # Alternative data — legacy columns retained for backward compatibility
    # during the JSON→relational migration.  New writes go to
    # AlternativeCalculation; these will be dropped in a future migration.
    alternatives = models.JSONField(null=True, blank=True, default=list)
    alternative_matrices = models.JSONField(null=True, blank=True, default=list)
    alternative_scores = models.JSONField(null=True, blank=True, default=list)
    ranking_data = models.JSONField(null=True, blank=True, default=list)
    ranking_list = models.JSONField(null=True, blank=True, default=list)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # alternative_count kept for migration period; will be removed once
    # AlternativeCalculation.objects.filter(project=...).count() is the
    # canonical source.
    alternative_count = models.IntegerField(default=0)

    # alternative_limit removed — limits now come from
    # settings.DEFAULT_ALTERNATIVE_LIMIT (Phase 3: subscription plans).

    class Meta:
        db_table = 'ahp_api_ahpproject'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user'], name='ahpproject_user_idx'),
            models.Index(fields=['created_at'], name='ahpproject_created_idx'),
        ]

    def __str__(self):
        return f"{self.project_name} ({self.get_project_type_display()})"

    def has_alternatives(self):
        return self.project_type == 'full_analysis'

    def get_alternative_count(self):
        """Live count from the relational table."""
        return self.alternative_calculations.count()

    def get_alternative_history_count(self):
        """Alias kept for backward compatibility with existing serializer code."""
        return self.get_alternative_count()


class AlternativeCalculation(models.Model):
    """One row per alternative calculation run for a project.

    Replaces the timestamp-keyed JSON blob in AHPProject.alternative_matrices.
    Using a proper relational model enables indexed queries, pagination, and
    foreign-key integrity — all required for scalable SaaS history features.
    """

    project = models.ForeignKey(
        AHPProject,
        on_delete=models.CASCADE,
        related_name='alternative_calculations',
    )
    alternatives = models.JSONField()            # list[str] — names of alternatives
    scores = models.JSONField()                  # {alt: {criterion: score}} raw 1-10 inputs
    ranking = models.JSONField()                 # list[str] — ordered best-first
    final_scores = models.JSONField()            # {alt: float} weighted scores
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'ahp_api_alternativecalculation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project'], name='altcalc_project_idx'),
            models.Index(fields=['created_at'], name='altcalc_created_idx'),
        ]

    def __str__(self):
        top = self.ranking[0] if self.ranking else '?'
        return f"Calc {self.id} — project {self.project_id} — winner: {top}"
