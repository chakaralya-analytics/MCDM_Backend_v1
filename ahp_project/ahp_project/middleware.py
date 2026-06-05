"""
middleware.py — Request-ID correlation, CSP security headers, audit logging.
"""

import logging
import threading
import time
import uuid

logger = logging.getLogger(__name__)

# Thread-local storage for the current request ID.
_local = threading.local()


def get_request_id() -> str:
    """Return the current request ID, or 'no-request' outside a request context."""
    return getattr(_local, 'request_id', 'no-request')


# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware:
    """Inject a unique request_id into every request.

    Priority:
      1. X-Request-ID header from upstream proxy / load balancer.
      2. Freshly generated UUID4.

    The id is stored in:
      - request.request_id      → accessible in views
      - threading.local()       → accessible in logging filter below
      - X-Request-ID response header → enables end-to-end tracing
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (
            request.META.get('HTTP_X_REQUEST_ID', '').strip()[:64]
            or str(uuid.uuid4())
        )
        _local.request_id = request_id
        request.request_id = request_id

        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000)

        response['X-Request-ID'] = request_id

        # Structured access log (omit health probes to reduce noise).
        if not request.path.startswith('/health/'):
            user_id = request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None
            logger.info(
                '%s %s %s %dms',
                request.method, request.path, response.status_code, duration_ms,
                extra={
                    'request_id': request_id,
                    'user_id': user_id,
                    'method': request.method,
                    'path': request.path,
                    'status': response.status_code,
                    'duration_ms': duration_ms,
                },
            )

        return response


# ---------------------------------------------------------------------------
# Logging filter — attaches request_id to every log record in this thread
# ---------------------------------------------------------------------------

class RequestIDFilter(logging.Filter):
    """Add request_id (and optionally user_id) to every log record.

    Configured as a filter on all handlers in settings.LOGGING so that every
    log line emitted during a request carries the correlation ID.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

_CSP = (
    "default-src 'self'; "
    # Razorpay checkout JS (loaded dynamically from CDN)
    "script-src 'self' 'unsafe-inline' https://checkout.razorpay.com; "
    # Razorpay frames & API calls
    "frame-src https://api.razorpay.com https://checkout.razorpay.com; "
    "connect-src 'self' https://api.razorpay.com https://lumberjack.razorpay.com; "
    # Favicon / plan images hosted externally
    "img-src 'self' data: https://cdn.razorpay.com; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)


class SecurityHeadersMiddleware:
    """Add security headers to every response.

    These supplement (but do not replace) any headers set by Nginx in production.
    The CSP is intentionally permissive for Razorpay — tighten if you remove it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only set on HTML responses — skip API JSON and static files.
        content_type = response.get('Content-Type', '')
        if 'text/html' in content_type or not response.get('Content-Type'):
            response['Content-Security-Policy'] = _CSP

        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('X-Frame-Options', 'DENY')
        response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=()',
        )

        return response
