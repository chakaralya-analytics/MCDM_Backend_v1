"""
subscription_service.py — all subscription business logic.

Views and other services call these functions; they never reach into the
plans models directly.  All quota enforcement goes through check_quota()
so the logic lives in one place and views stay thin.
"""

import logging
from django.db import transaction
from django.utils import timezone

from ..models import SubscriptionPlan, UserSubscription

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def get_free_plan():
    """Return the active Free plan.  Raises SubscriptionPlan.DoesNotExist if missing."""
    return SubscriptionPlan.objects.get(name=SubscriptionPlan.PLAN_FREE, is_active=True)


def get_or_create_subscription(user):
    """Return the user's subscription, creating a free one if none exists.

    This is the safe entry point used by all quota checks.  An existing user
    who predates the plans system will automatically receive a free plan.
    """
    try:
        return user.subscription
    except UserSubscription.DoesNotExist:
        return create_free_subscription(user)


def get_active_subscription(user):
    """Return the subscription if it is currently active, else None."""
    sub = get_or_create_subscription(user)
    return sub if sub.is_active else None


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def create_free_subscription(user):
    """Create and return a free-tier subscription for *user*."""
    free_plan = get_free_plan()
    with transaction.atomic():
        sub = UserSubscription.objects.create(
            user=user,
            plan=free_plan,
            status=UserSubscription.STATUS_ACTIVE,
            starts_at=timezone.now(),
            ends_at=None,       # Free plan never expires
            auto_renew=False,
            provider=UserSubscription.PROVIDER_INTERNAL,
        )
    logger.info("Created free subscription for user id=%s", user.id)
    return sub


def upgrade_subscription(user, plan_name, billing_cycle='monthly'):
    """Switch the user to a different plan.

    No payment processing here — the payment hook (Phase 4) will call this
    after a successful charge.
    """
    try:
        new_plan = SubscriptionPlan.objects.get(name=plan_name, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        raise ValueError(f"Plan '{plan_name}' not found or not active.")

    with transaction.atomic():
        sub = get_or_create_subscription(user)
        old_name = sub.plan.name
        sub.plan = new_plan
        sub.billing_cycle = billing_cycle
        sub.status = UserSubscription.STATUS_ACTIVE
        sub.cancelled_at = None
        sub.save(update_fields=['plan', 'billing_cycle', 'status', 'cancelled_at', 'updated_at'])

    logger.info("Plan changed for user id=%s: %s → %s", user.id, old_name, plan_name)
    return sub


def cancel_subscription(user):
    """Mark the subscription as cancelled.

    Access continues until ends_at (if set); for Free plans ends_at is None
    so cancellation is instant.
    """
    sub = get_or_create_subscription(user)
    sub.status = UserSubscription.STATUS_CANCELLED
    sub.cancelled_at = timezone.now()
    sub.auto_renew = False
    sub.save(update_fields=['status', 'cancelled_at', 'auto_renew', 'updated_at'])
    logger.info("Subscription cancelled for user id=%s", user.id)
    return sub


# ---------------------------------------------------------------------------
# Quota enforcement
# ---------------------------------------------------------------------------

def _quota_response(plan, resource, used, limit, allowed):
    """Build a standardised quota dict returned by check_* functions."""
    return {
        'allowed': allowed,
        'resource': resource,
        'current_plan': plan.name,
        'current_plan_display': plan.display_name,
        'usage': {
            'used': used,
            'limit': limit,
            'unlimited': limit is None,
        },
        'upgrade_required': not allowed,
        'error': f"Limit reached for {resource}" if not allowed else None,
    }


def check_project_quota(user):
    """Return (allowed: bool, quota_info: dict) for creating a new project."""
    from ahp_api.models import AHPProject

    sub = get_or_create_subscription(user)
    plan = sub.plan
    limit = plan.max_projects
    used = AHPProject.objects.filter(user=user).count()

    if limit is None:
        return True, _quota_response(plan, 'projects', used, None, True)

    allowed = used < limit
    return allowed, _quota_response(plan, 'projects', used, limit, allowed)


def check_alternative_quota(project):
    """Return (allowed: bool, quota_info: dict) for adding an alternative calc."""
    from ahp_api.models import AlternativeCalculation

    user = project.user
    sub = get_or_create_subscription(user)
    plan = sub.plan
    limit = plan.max_alternatives_per_project
    used = AlternativeCalculation.objects.filter(project=project).count()

    if limit is None:
        return True, _quota_response(plan, 'alternatives_per_project', used, None, True)

    allowed = used < limit
    return allowed, _quota_response(plan, 'alternatives_per_project', used, limit, allowed)


def check_criteria_quota(user, criteria_count):
    """Return (allowed: bool, quota_info: dict) for a given criteria count."""
    sub = get_or_create_subscription(user)
    plan = sub.plan
    limit = plan.max_criteria

    if limit is None:
        return True, _quota_response(plan, 'criteria', criteria_count, None, True)

    allowed = criteria_count <= limit
    return allowed, _quota_response(plan, 'criteria', criteria_count, limit, allowed)


# ---------------------------------------------------------------------------
# Info / reporting
# ---------------------------------------------------------------------------

def get_subscription_info(user):
    """Return a comprehensive dict with plan, subscription status, and live usage."""
    from ahp_api.models import AHPProject, AlternativeCalculation

    sub = get_or_create_subscription(user)
    plan = sub.plan

    project_count = AHPProject.objects.filter(user=user).count()
    alt_count = AlternativeCalculation.objects.filter(project__user=user).count()

    def _usage(used, limit):
        return {
            'used': used,
            'limit': limit,
            'unlimited': limit is None,
            'percent': (
                0 if limit is None or limit == 0
                else min(100, round(used / limit * 100))
            ),
        }

    return {
        'plan': {
            'name': plan.name,
            'display_name': plan.display_name,
            'description': plan.description,
            'monthly_price': str(plan.monthly_price),
            'yearly_price': str(plan.yearly_price),
            'feature_flags': plan.feature_flags,
            'sort_order': plan.sort_order,
        },
        'subscription': {
            'status': sub.status,
            'billing_cycle': sub.billing_cycle,
            'is_active': sub.is_active,
            'is_trial': sub.is_trial,
            'starts_at': sub.starts_at.isoformat() if sub.starts_at else None,
            'ends_at': sub.ends_at.isoformat() if sub.ends_at else None,
            'remaining_days': sub.remaining_days(),
            'auto_renew': sub.auto_renew,
            'provider': sub.provider,
        },
        'usage': {
            'projects': _usage(project_count, plan.max_projects),
            'alternatives': _usage(alt_count, plan.max_alternatives_per_project),
            'criteria': _usage(plan.max_criteria or 0, plan.max_criteria),
            'experts': _usage(plan.max_experts or 0, plan.max_experts),
        },
    }
