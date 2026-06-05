# billing/serializers.py

from rest_framework import serializers

from plans.models import SubscriptionPlan, UserSubscription
from .models import PaymentRecord


class CreateOrderSerializer(serializers.Serializer):
    """Validate the create-order request.

    plan must be pro or enterprise — you cannot pay for the Free plan.
    billing_cycle defaults to monthly.
    Amount is NEVER accepted from the frontend; it is calculated server-side.
    """
    plan = serializers.ChoiceField(
        choices=[
            SubscriptionPlan.PLAN_PRO,
            SubscriptionPlan.PLAN_ENTERPRISE,
        ],
        required=False,
    )
    billing_cycle = serializers.ChoiceField(
        choices=[UserSubscription.CYCLE_MONTHLY, UserSubscription.CYCLE_YEARLY],
        default=UserSubscription.CYCLE_MONTHLY,
    )
    credit_pack = serializers.ChoiceField(
        choices=['starter', 'growth', 'pro'],
        required=False,
    )

    def validate(self, attrs):
        plan = attrs.get('plan')
        credit_pack = attrs.get('credit_pack')

        if bool(plan) == bool(credit_pack):
            raise serializers.ValidationError(
                "Send exactly one of 'plan' or 'credit_pack'."
            )

        return attrs


class VerifyPaymentSerializer(serializers.Serializer):
    """Validate the verify-payment request — all three fields are mandatory."""
    razorpay_order_id = serializers.CharField(max_length=255)
    razorpay_payment_id = serializers.CharField(max_length=255)
    razorpay_signature = serializers.CharField(max_length=500)


class PaymentRecordSerializer(serializers.ModelSerializer):
    amount_rupees = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    billing_cycle = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRecord
        fields = [
            'id',
            'provider',
            'payment_id',
            'order_id',
            'amount',
            'amount_rupees',
            'currency',
            'status',
            'payment_method',
            'plan_name',
            'billing_cycle',
            'paid_at',
            'created_at',
        ]
        read_only_fields = fields

    def get_amount_rupees(self, obj):
        return round(obj.amount / 100, 2)

    def get_plan_name(self, obj):
        return obj.metadata.get('plan', '')

    def get_billing_cycle(self, obj):
        return obj.metadata.get('billing_cycle', '')
