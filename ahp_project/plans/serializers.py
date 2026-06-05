# plans/serializers.py

from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription
from .services import subscription_service


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name', 'display_name', 'description',
            'monthly_price', 'yearly_price',
            'max_projects', 'max_alternatives_per_project',
            'max_criteria', 'max_experts',
            'feature_flags', 'sort_order',
        ]


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    remaining_days = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'plan', 'status', 'billing_cycle', 'is_active', 'is_trial',
            'starts_at', 'ends_at', 'cancelled_at', 'remaining_days',
            'auto_renew', 'provider',
        ]

    def get_remaining_days(self, obj):
        return obj.remaining_days()


class ChangePlanSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=[
        SubscriptionPlan.PLAN_FREE,
        SubscriptionPlan.PLAN_PRO,
        SubscriptionPlan.PLAN_ENTERPRISE,
    ])
    billing_cycle = serializers.ChoiceField(
        choices=[UserSubscription.CYCLE_MONTHLY, UserSubscription.CYCLE_YEARLY],
        default=UserSubscription.CYCLE_MONTHLY,
    )
