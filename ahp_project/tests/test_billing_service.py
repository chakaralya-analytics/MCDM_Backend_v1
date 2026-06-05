"""Tests for the billing service layer."""

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from billing.services.billing_service import (
    _verify_payment_signature,
    create_order,
    verify_payment,
)


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _make_sig(key_secret: str, order_id: str, payment_id: str) -> str:
    msg = f'{order_id}|{payment_id}'
    return hmac.new(key_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


@pytest.mark.django_db
def test_valid_payment_signature_accepted(settings):
    settings.RAZORPAY_KEY_SECRET = 'test_key_secret'
    sig = _make_sig('test_key_secret', 'order_abc', 'pay_xyz')
    # Should not raise
    _verify_payment_signature('order_abc', 'pay_xyz', sig)


@pytest.mark.django_db
def test_invalid_payment_signature_raises(settings):
    settings.RAZORPAY_KEY_SECRET = 'test_key_secret'
    with pytest.raises(ValueError, match='signature'):
        _verify_payment_signature('order_abc', 'pay_xyz', 'bad_signature')


# ---------------------------------------------------------------------------
# create_order
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_create_order_free_plan_raises(user, free_plan, pro_plan):
    with pytest.raises(ValueError, match='free'):
        create_order(user, 'free', 'monthly')


@pytest.mark.django_db
def test_create_order_unknown_plan_raises(user, pro_plan):
    with pytest.raises(ValueError):
        create_order(user, 'nonexistent_plan', 'monthly')


@pytest.mark.django_db
def test_create_order_returns_expected_keys(user, pro_plan, settings):
    settings.RAZORPAY_KEY_ID = 'rzp_test_key'
    settings.RAZORPAY_KEY_SECRET = 'rzp_test_secret'

    mock_order = {'id': 'order_test123', 'amount': pro_plan.monthly_price, 'currency': 'INR'}

    with patch('billing.services.billing_service._razorpay_client') as mock_client_fn:
        mock_client = MagicMock()
        mock_client.order.create.return_value = mock_order
        mock_client_fn.return_value = mock_client

        result = create_order(user, 'pro', 'monthly')

    assert result['order_id'] == 'order_test123'
    assert result['plan'] == 'pro'
    assert 'key' in result
    assert 'amount' in result

    from billing.models import PaymentRecord
    record = PaymentRecord.objects.get(order_id='order_test123')
    assert record.status == PaymentRecord.STATUS_PENDING
    assert record.user == user


# ---------------------------------------------------------------------------
# verify_payment — idempotency
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_verify_payment_idempotent(user, pro_plan, settings):
    """Calling verify_payment twice returns the same record without errors."""
    settings.RAZORPAY_KEY_SECRET = 'rzp_test_secret'
    from billing.models import PaymentRecord

    # Pre-create a PAID record to simulate double callback.
    record = PaymentRecord.objects.create(
        user=user,
        order_id='order_idem',
        payment_id='pay_idem',
        amount=pro_plan.monthly_price,
        currency='INR',
        status=PaymentRecord.STATUS_PAID,
        provider=PaymentRecord.PROVIDER_RAZORPAY,
        metadata={'plan_name': 'pro', 'billing_cycle': 'monthly'},
    )

    sig = _make_sig('rzp_test_secret', 'order_idem', 'pay_idem')
    result = verify_payment(user, 'order_idem', 'pay_idem', sig)
    assert result.id == record.id
    assert result.status == PaymentRecord.STATUS_PAID
