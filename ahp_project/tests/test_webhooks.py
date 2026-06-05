"""Tests for the Razorpay webhook endpoint."""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.urls import reverse


WEBHOOK_URL = '/api/v1/billing/webhook/razorpay/'

_PAYMENT_CAPTURED_PAYLOAD = {
    'id': 'evt_test_001',
    'entity': 'event',
    'event': 'payment.captured',
    'payload': {
        'payment': {
            'entity': {
                'id': 'pay_test_001',
                'order_id': 'order_test_001',
                'amount': 99900,
                'currency': 'INR',
                'status': 'captured',
            }
        }
    },
    'account_id': 'acc_test',
    'created_at': 1700000000,
}


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.django_db
def test_webhook_missing_signature_returns_400(client, settings):
    settings.RAZORPAY_WEBHOOK_SECRET = 'webhook_secret'
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(_PAYMENT_CAPTURED_PAYLOAD),
        content_type='application/json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_webhook_invalid_signature_returns_400(client, settings):
    settings.RAZORPAY_WEBHOOK_SECRET = 'webhook_secret'
    resp = client.post(
        WEBHOOK_URL,
        data=json.dumps(_PAYMENT_CAPTURED_PAYLOAD),
        content_type='application/json',
        HTTP_X_RAZORPAY_SIGNATURE='bad_signature',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_webhook_valid_signature_returns_200(client, settings):
    settings.RAZORPAY_WEBHOOK_SECRET = 'webhook_secret'
    body = json.dumps(_PAYMENT_CAPTURED_PAYLOAD).encode()
    sig = _sign('webhook_secret', body)

    with patch('billing.tasks.process_webhook_event_task.delay'):
        resp = client.post(
            WEBHOOK_URL,
            data=body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )

    assert resp.status_code == 200


@pytest.mark.django_db
def test_webhook_duplicate_event_returns_200(client, settings):
    """Duplicate delivery of the same event_id must be accepted silently."""
    settings.RAZORPAY_WEBHOOK_SECRET = 'webhook_secret'
    body = json.dumps(_PAYMENT_CAPTURED_PAYLOAD).encode()
    sig = _sign('webhook_secret', body)

    with patch('billing.tasks.process_webhook_event_task.delay'):
        resp1 = client.post(
            WEBHOOK_URL, data=body, content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )
        resp2 = client.post(
            WEBHOOK_URL, data=body, content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    from billing.models import WebhookEvent
    assert WebhookEvent.objects.filter(event_id='evt_test_001').count() == 1
