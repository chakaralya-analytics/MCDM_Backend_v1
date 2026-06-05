"""Tests for subscription quota enforcement."""

import pytest
from plans.services.subscription_service import (
    check_project_quota,
    check_alternative_quota,
)


@pytest.mark.django_db
def test_free_plan_allows_up_to_max_projects(user, free_plan):
    """New user starts with 0 projects — quota allows creation."""
    allowed, quota = check_project_quota(user)
    assert allowed is True
    assert quota['usage']['used'] == 0
    assert quota['usage']['limit'] == free_plan.max_projects


@pytest.mark.django_db
def test_free_plan_blocks_when_at_limit(user, free_plan):
    """After creating max_projects, the quota check must deny."""
    from ahp_api.models import Project
    for i in range(free_plan.max_projects):
        Project.objects.create(user=user, name=f'P{i}', criteria=['A', 'B'])

    allowed, quota = check_project_quota(user)
    assert allowed is False
    assert quota['upgrade_required'] is True
    assert quota['usage']['used'] == free_plan.max_projects


@pytest.mark.django_db
def test_pro_plan_has_higher_project_limit(make_user, pro_plan, free_plan):
    """Upgrading to Pro raises the effective limit."""
    from plans.services.subscription_service import upgrade_subscription
    u = make_user()
    upgrade_subscription(u, 'pro')

    allowed, quota = check_project_quota(u)
    assert allowed is True
    assert quota['usage']['limit'] == pro_plan.max_projects


@pytest.mark.django_db
def test_alternative_quota_enforced_per_project(user, free_plan):
    """Alternatives are counted per-project, not globally."""
    from ahp_api.models import Project, Alternative
    project = Project.objects.create(user=user, name='P1', criteria=['A', 'B'])

    # Fill up to the limit
    for i in range(free_plan.max_alternatives_per_project):
        Alternative.objects.create(project=project, name=f'Alt{i}')

    allowed, quota = check_alternative_quota(project)
    assert allowed is False
    assert quota['upgrade_required'] is True
