# ahp_api/serializers.py

from rest_framework import serializers
from .models import AHPProject, AlternativeCalculation


# ---------------------------------------------------------------------------
# Input serializers
# ---------------------------------------------------------------------------

class AHPCriteriaInputSerializer(serializers.Serializer):
    project_name = serializers.CharField(max_length=200)
    criteria = serializers.ListField(
        child=serializers.CharField(min_length=1, max_length=100),
        min_length=2,
    )
    pairwise_matrix = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
    )

    def validate_criteria(self, value):
        lower = [c.lower().strip() for c in value]
        if len(set(lower)) != len(lower):
            raise serializers.ValidationError("Criteria names must be unique (case-insensitive).")
        return value


class AHPAlternativesScoringSerializer(serializers.Serializer):
    """Input validator for the alternative scoring endpoint."""
    project_id = serializers.IntegerField()
    alternatives = serializers.ListField(
        child=serializers.CharField(min_length=1, max_length=200),
        min_length=1,
    )
    alternative_scores = serializers.DictField(
        child=serializers.DictField(
            child=serializers.FloatField(min_value=1, max_value=10)
        )
    )

    def validate(self, attrs):
        alternatives = attrs['alternatives']
        scores = attrs['alternative_scores']

        missing = [a for a in alternatives if a not in scores]
        if missing:
            raise serializers.ValidationError(
                f"Scores missing for alternatives: {missing}"
            )
        return attrs


# ---------------------------------------------------------------------------
# Output serializers
# ---------------------------------------------------------------------------

class AHPProjectListSerializer(serializers.ModelSerializer):
    """Minimal project list (for the 'all projects' view)."""
    alternative_count = serializers.SerializerMethodField()

    class Meta:
        model = AHPProject
        fields = ['id', 'project_name', 'created_at', 'updated_at',
                  'project_type', 'alternative_count']

    def get_alternative_count(self, obj):
        return obj.get_alternative_count()


class AHPProjectDetailSerializer(serializers.ModelSerializer):
    """Full project detail including history summary."""
    alternative_count = serializers.SerializerMethodField()
    alternative_history_summary = serializers.SerializerMethodField()
    # Ensure weights is never null in responses — serializer handles the
    # guarantee so views don't need a transform_project_response() patch.
    weights = serializers.SerializerMethodField()

    class Meta:
        model = AHPProject
        fields = [
            'id', 'project_name', 'criteria', 'weights', 'consistency_ratio',
            'pairwise_matrix', 'alternatives', 'alternative_scores',
            'ranking_list', 'ranking_data', 'created_at', 'updated_at',
            'project_type', 'alternative_count', 'alternative_history_summary',
        ]

    def get_weights(self, obj):
        w = obj.weights
        if not isinstance(w, list):
            return []
        return w

    def get_alternative_count(self, obj):
        return obj.get_alternative_count()

    def get_alternative_history_summary(self, obj):
        calcs = (
            AlternativeCalculation.objects
            .filter(project=obj)
            .order_by('-created_at')
            .values('id', 'created_at', 'alternatives')
        )
        return [
            {
                'id': c['id'],
                'created_at': c['created_at'].isoformat(),
                'count': len(c['alternatives'] or []),
                'alternatives': c['alternatives'] or [],
            }
            for c in calcs
        ]


class CriteriaOnlyProjectSerializer(serializers.ModelSerializer):
    """Dashboard project list — includes live alternative limits."""
    alternative_count = serializers.SerializerMethodField()
    alternative_limits = serializers.SerializerMethodField()
    weights = serializers.SerializerMethodField()

    class Meta:
        model = AHPProject
        fields = [
            'id', 'project_name', 'criteria', 'weights', 'consistency_ratio',
            'created_at', 'project_type', 'alternative_count', 'alternative_limits',
        ]

    def get_weights(self, obj):
        w = obj.weights
        if not isinstance(w, list):
            return []
        return w

    def get_alternative_count(self, obj):
        return obj.get_alternative_count()

    def get_alternative_limits(self, obj):
        from .services.project_service import get_alternative_limits
        return get_alternative_limits(obj)


class AlternativeCalculationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlternativeCalculation
        fields = ['id', 'alternatives', 'scores', 'ranking', 'final_scores', 'created_at']
