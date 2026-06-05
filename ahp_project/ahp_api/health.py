"""
health.py — Kubernetes / Docker health probe endpoints.

  GET /health/live  — liveness:  always 200 while the process responds
  GET /health/ready — readiness: 200 if the DB is reachable, 503 otherwise

Cache failure is reported but does NOT flip the readiness to 503 because the
app can serve requests from local memory cache when Redis is unavailable.

No authentication required. Responses never leak exception details.
"""

import logging

from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def liveness(request):
    """GET /health/live — process is alive and event loop is not blocked."""
    return JsonResponse({'status': 'ok'})


def readiness(request):
    """GET /health/ready — critical dependencies are reachable.

    Returns 200 (ok / degraded) or 503 (error).
    503 is only returned when the primary database is unreachable so that
    load-balancers / orchestrators pull this instance from rotation.
    """
    checks: dict = {}
    db_ok = True

    # --- Database (required) ---
    try:
        with connections['default'].cursor() as cur:
            cur.execute('SELECT 1')
        checks['db'] = 'ok'
    except Exception:
        logger.exception('Readiness probe: database check failed')
        checks['db'] = 'error'
        db_ok = False

    # --- Cache (optional — degraded, not fatal) ---
    try:
        _key = '_health_ready_probe'
        cache.set(_key, '1', timeout=10)
        checks['cache'] = 'ok' if cache.get(_key) == '1' else 'miss'
    except Exception:
        logger.warning('Readiness probe: cache check failed')
        checks['cache'] = 'error'

    if db_ok:
        overall = 'ok' if checks.get('cache') == 'ok' else 'degraded'
        http_status = 200
    else:
        overall = 'error'
        http_status = 503

    return JsonResponse({'status': overall, 'checks': checks}, status=http_status)
