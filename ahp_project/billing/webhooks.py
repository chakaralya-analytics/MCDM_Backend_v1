# billing/webhooks.py
#
# This module is intentionally separate from views.py because:
#   1. The webhook endpoint must be CSRF-exempt (provider POSTs without a cookie).
#   2. We need access to the raw request body (request.body) before any
#      middleware touches it — signature verification requires the exact bytes.
#   3. It processes events asynchronously via Celery; views return HTTP responses.

import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services.billing_service import (
    store_webhook_event,
    verify_razorpay_webhook_signature,
)
from .tasks import process_webhook_event_task

logger = logging.getLogger(__name__)

_RAZORPAY_SIG_HEADER = 'HTTP_X_RAZORPAY_SIGNATURE'


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """POST /api/v1/billing/webhook/razorpay/

    Security flow:
      1. Extract X-Razorpay-Signature header.
      2. Verify HMAC-SHA256 of raw body with RAZORPAY_WEBHOOK_SECRET.
         Reject immediately on mismatch — no payload is parsed.
      3. Parse JSON; extract a stable event_id for idempotency.
      4. Persist WebhookEvent (unique on event_id).
      5. Enqueue Celery task for async processing.
      6. Return HTTP 200 immediately so Razorpay does not retry.
    """
    raw_body = request.body
    received_sig = request.META.get(_RAZORPAY_SIG_HEADER, '')

    if not received_sig:
        logger.warning("Razorpay webhook received without signature header")
        return HttpResponse(status=400)

    if not verify_razorpay_webhook_signature(raw_body, received_sig):
        logger.warning("Razorpay webhook signature verification failed")
        return HttpResponse(status=400)

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Razorpay webhook: malformed JSON body")
        return HttpResponse(status=400)

    event_type = payload.get('event', '')
    account_id = payload.get('account_id', 'unknown')
    created_at = payload.get('created_at', '')

    # Build a stable, unique event_id for idempotency.
    # Razorpay may include a top-level 'id' field; fall back to entity ID
    # or a compound key so we never skip deduplication.
    event_id = (
        payload.get('id')
        or _extract_primary_entity_id(payload)
        or f"{account_id}_{event_type}_{created_at}"
    )

    event, created = store_webhook_event(
        provider='razorpay',
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )

    if not created:
        logger.info("Razorpay webhook: duplicate event %s — acknowledged", event_id)
        return HttpResponse(status=200)

    if event:
        process_webhook_event_task.delay(event.id)

    return HttpResponse(status=200)


def _extract_primary_entity_id(payload: dict) -> str:
    """Best-effort extraction of the primary entity ID from a Razorpay webhook."""
    try:
        entities = payload.get('payload', {})
        for key in ('payment', 'subscription', 'refund', 'order'):
            if key in entities:
                entity_id = entities[key]['entity']['id']
                return f"{key}_{entity_id}"
    except (KeyError, TypeError):
        pass
    return ''
