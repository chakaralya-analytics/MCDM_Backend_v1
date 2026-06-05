"""
project_service.py — all project-related business logic.

Views call these functions; they never reach into models directly.
This layer is the right place for limit checks, ownership validation,
and any cross-model coordination.
"""

import logging
from django.db import transaction

from ..models import AHPProject

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_projects_for_user(user, with_weights=False):
    """Return an ordered queryset of projects belonging to *user*.

    If *with_weights* is True, only return projects that have weights
    calculated (i.e. the criteria phase is complete).
    """
    qs = AHPProject.objects.filter(user=user).order_by('-created_at')
    if with_weights:
        qs = qs.filter(weights__isnull=False)
    return qs


def get_project_for_user(project_id, user):
    """Return the project owned by *user* with the given *project_id*.

    Raises AHPProject.DoesNotExist if not found or not owned by the user.
    """
    return AHPProject.objects.get(id=project_id, user=user)


# ---------------------------------------------------------------------------
# Limit checks  (sourced from subscription plan via subscription_service)
# ---------------------------------------------------------------------------

def get_project_limits(user):
    """Return a dict describing the user's current project usage and limits."""
    from plans.services.subscription_service import check_project_quota
    allowed, quota = check_project_quota(user)
    return {
        'max_projects': quota['usage']['limit'],
        'current_projects': quota['usage']['used'],
        'can_create_more': allowed,
        'unlimited': quota['usage']['unlimited'],
    }


def check_can_create_project(user):
    """Return (allowed: bool, quota_info: dict) from the subscription plan."""
    from plans.services.subscription_service import check_project_quota
    return check_project_quota(user)


def get_alternative_limits(project):
    """Return a dict describing alternative usage for *project*."""
    from plans.services.subscription_service import check_alternative_quota
    allowed, quota = check_alternative_quota(project)
    return {
        'max_alternatives': quota['usage']['limit'],
        'current_alternatives': quota['usage']['used'],
        'can_add_more': allowed,
        'unlimited': quota['usage']['unlimited'],
    }


def check_can_add_alternative(project):
    """Return (allowed: bool, quota_info: dict) from the subscription plan."""
    from plans.services.subscription_service import check_alternative_quota
    return check_alternative_quota(project)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def create_criteria_project(user, project_name, criteria, pairwise_matrix,
                             weights, consistency_ratio):
    """Persist a new criteria-only project and return the saved instance."""
    project = AHPProject.objects.create(
        user=user,
        project_name=project_name,
        project_type='criteria_only',
        criteria=criteria,
        pairwise_matrix=pairwise_matrix,
        weights=weights,
        consistency_ratio=consistency_ratio,
    )
    logger.info(
        "Created criteria project id=%s name=%r for user=%s",
        project.id, project_name, user.id,
    )
    return project
