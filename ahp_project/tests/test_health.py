"""Tests for health probe endpoints."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_liveness_always_200(client):
    resp = client.get('/health/live')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


@pytest.mark.django_db
def test_readiness_ok_with_sqlite(client):
    """SQLite is always reachable in the test environment."""
    resp = client.get('/health/ready')
    # May be 'ok' or 'degraded' (if cache misses) but never 503 with SQLite.
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] in ('ok', 'degraded')
    assert data['checks']['db'] == 'ok'


@pytest.mark.django_db
def test_readiness_503_when_db_unreachable(client, settings, monkeypatch):
    """When the DB check raises, readiness must return 503."""
    from django.db.backends.utils import CursorWrapper

    def _raise(*args, **kwargs):
        raise Exception('simulated DB failure')

    monkeypatch.setattr(CursorWrapper, 'execute', _raise)
    resp = client.get('/health/ready')
    assert resp.status_code == 503
    assert resp.json()['checks']['db'] == 'error'
