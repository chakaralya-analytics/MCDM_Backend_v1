# plans/decorators.py

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .services import subscription_service


def require_feature(feature_name):
    """Reject the request with 403 if the user's plan lacks *feature_name*."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            sub = subscription_service.get_or_create_subscription(request.user)
            if not sub.has_feature(feature_name):
                return Response(
                    {
                        'error': f"Feature '{feature_name}' is not available on your current plan.",
                        'feature': feature_name,
                        'current_plan': sub.plan.name,
                        'upgrade_required': True,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_plan(*plan_names):
    """Reject the request with 403 if the user is not on one of *plan_names*."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            sub = subscription_service.get_or_create_subscription(request.user)
            if sub.plan.name not in plan_names:
                return Response(
                    {
                        'error': f"This action requires one of the following plans: {', '.join(plan_names)}.",
                        'required_plans': list(plan_names),
                        'current_plan': sub.plan.name,
                        'upgrade_required': True,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator
