"""
conftest.py — Shared pytest fixtures for the AHP-TOPSIS API test suite.

Environment requirements:
  - USE_SQLITE=True  (or set in pytest.ini via env)
  - SECRET_KEY=test-secret-key-not-for-production

Run:
    USE_SQLITE=True SECRET_KEY=testing pytest
"""

import os
import pytest

# Force SQLite for all tests — fast, no external service required.
os.environ.setdefault('USE_SQLITE', 'True')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production-only')

from django.contrib.auth.models import User
from rest_framework.test import APIClient


# ---------------------------------------------------------------------------
# User + auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    """Factory fixture: make_user() → User with auto-provisioned free subscription."""
    _counter = [0]

    def _make(username=None, email=None, password='testpass123'):
        _counter[0] += 1
        n = _counter[0]
        u = User.objects.create_user(
            username=username or f'user{n}',
            email=email or f'user{n}@example.com',
            password=password,
        )
        # Provision free subscription — mirrors what RegisterView does.
        from plans.services.subscription_service import create_free_subscription
        create_free_subscription(u)
        return u

    return _make


@pytest.fixture
def user(make_user):
    """A single ready-to-use test user."""
    return make_user()


@pytest.fixture
def auth_client(user):
    """APIClient authenticated as *user* via JWT."""
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    tokens = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens.access_token}')
    return client


# ---------------------------------------------------------------------------
# Plan fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def free_plan(db):
    from plans.models import SubscriptionPlan
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name='free',
        defaults={
            'display_name': 'Free',
            'monthly_price': 0,
            'yearly_price': 0,
            'max_projects': 2,
            'max_alternatives_per_project': 3,
            'max_criteria': 5,
            'max_experts': 1,
        },
    )
    return plan


@pytest.fixture
def pro_plan(db):
    from plans.models import SubscriptionPlan
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name='pro',
        defaults={
            'display_name': 'Pro',
            'monthly_price': 99900,
            'yearly_price': 999900,
            'max_projects': 20,
            'max_alternatives_per_project': 20,
            'max_criteria': 20,
            'max_experts': 5,
        },
    )
    return plan
