# plans/permissions.py

from rest_framework.permissions import BasePermission
from .services import subscription_service


class HasActiveSubscription(BasePermission):
    """Allow only users with an active (non-cancelled/expired) subscription.

    Free-tier users pass — 'active' covers both paid and free plans.
    """
    message = "Your subscription is not active."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        sub = subscription_service.get_active_subscription(request.user)
        return sub is not None
