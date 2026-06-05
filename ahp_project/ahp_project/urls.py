from django.contrib import admin
from django.urls import path, include
from ahp_api import health

urlpatterns = [
    # ── Health probes ─────────────────────────────────────────────────────────
    # No auth, no API prefix — compatible with K8s / Docker / Cloud Run.
    path('health/live', health.liveness, name='health_live'),
    path('health/ready', health.readiness, name='health_ready'),

    path('admin/', admin.site.urls),

    # ── Canonical v1 API ──────────────────────────────────────────────────────
    # Parent owns the full prefix; child urls.py uses relative paths only.
    path('api/v1/', include('ahp_api.urls')),        # /api/v1/calculate/, /api/v1/projects/...
    path('api/v1/users/', include('users.urls')),    # /api/v1/users/login/, /api/v1/users/register/
    path('api/v1/plans/', include('plans.urls')),    # /api/v1/plans/, /api/v1/plans/subscription/
    path('api/v1/billing/', include('billing.urls')), # /api/v1/billing/create-order/, /api/v1/billing/payments/

    # ── Backward-compatibility aliases ────────────────────────────────────────
    # Keep pre-v1 paths alive for any existing clients / scripts.
    path('api/', include('ahp_api.urls')),
    path('users/', include('users.urls')),
]
