# plans/views.py

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SubscriptionPlan
from .serializers import (
    ChangePlanSerializer,
    SubscriptionPlanSerializer,
    UserSubscriptionSerializer,
)
from .services import subscription_service, usage_service


class PlanListView(APIView):
    """GET /api/v1/plans/ — list all active plans, ordered by sort_order."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data)


class MySubscriptionView(APIView):
    """GET /api/v1/plans/subscription/ — current user's subscription + full info."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        info = subscription_service.get_subscription_info(request.user)
        return Response(info)


class ChangePlanView(APIView):
    """POST /api/v1/plans/subscription/change/ — switch to a different plan."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePlanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan_name = serializer.validated_data['plan']
        billing_cycle = serializer.validated_data['billing_cycle']

        try:
            sub = subscription_service.upgrade_subscription(
                request.user, plan_name, billing_cycle
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(UserSubscriptionSerializer(sub).data)


class CancelSubscriptionView(APIView):
    """POST /api/v1/plans/subscription/cancel/ — cancel the subscription."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = subscription_service.cancel_subscription(request.user)
        return Response(UserSubscriptionSerializer(sub).data)


class UsageView(APIView):
    """GET /api/v1/plans/usage/ — live quota status for all resources + monthly activity.

    Returns the same `usage` shape as /plans/subscription/ so callers can
    use either endpoint interchangeably.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        info = subscription_service.get_subscription_info(request.user)
        monthly = usage_service.get_current_usage(request.user)
        return Response({
            **info['usage'],                # projects, alternatives, criteria, experts
            'monthly_activity': monthly,    # projects_created, calculations_run, etc.
        })
