"""
billing_service.py — Razorpay payment processing and subscription lifecycle.

Security guarantees enforced here:
  • Amounts are calculated server-side from SubscriptionPlan.monthly/yearly_price.
    Frontend never supplies the price.
  • Payment signatures are verified via HMAC-SHA256 before any state mutation.
  • Webhook event_id uniqueness prevents duplicate processing.
  • select_for_update() prevents concurrent double-activation on the same order.
  • All subscription activations go through plans.subscription_service so plan
    logic stays in one place.
"""

import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from plans.models import SubscriptionPlan
from plans.services.subscription_service import (
    get_or_create_subscription,
    upgrade_subscription,
)
from ..models import PaymentRecord, WebhookEvent

logger = logging.getLogger(__name__)

CREDIT_PACKS = {
    'starter': {
        'name': 'Starter',
        'credits': 50,
        'amount_paise': 49900,
    },
    'growth': {
        'name': 'Growth',
        'credits': 125,
        'amount_paise': 99900,
    },
    'pro': {
        'name': 'Pro',
        'credits': 300,
        'amount_paise': 199900,
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _razorpay_client():
    import razorpay
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise PermissionError("Razorpay credentials are not configured.")
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def _hmac_sha256(key: str, message: str) -> str:
    return hmac.new(
        key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------

def create_order(user, plan_name: str, billing_cycle: str = 'monthly') -> dict:
    """Create a Razorpay order and a pending PaymentRecord.

    Returns the dict the frontend passes directly to the Razorpay checkout widget.
    Raises ValueError for invalid inputs (handled in view).
    """
    try:
        plan = SubscriptionPlan.objects.get(name=plan_name, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        raise ValueError(f"Plan '{plan_name}' not found or not active.")

    if plan.name == SubscriptionPlan.PLAN_FREE:
        raise ValueError("Cannot create a payment order for the Free plan.")

    price = plan.yearly_price if billing_cycle == 'yearly' else plan.monthly_price
    amount_paise = int(price * 100)

    if amount_paise < 100:
        raise ValueError("Minimum Razorpay order amount is 100 paise.")

    client = _razorpay_client()
    receipt = f"rcpt_{user.id}_{int(timezone.now().timestamp())}"
    rz_order = client.order.create({
        'amount': amount_paise,
        'currency': settings.RAZORPAY_CURRENCY,
        'receipt': receipt,
        'notes': {
            'user_id': str(user.id),
            'username': user.username,
            'plan': plan_name,
            'billing_cycle': billing_cycle,
        },
    })

    sub = get_or_create_subscription(user)
    record = PaymentRecord.objects.create(
        user=user,
        subscription=sub,
        provider=PaymentRecord.PROVIDER_RAZORPAY,
        order_id=rz_order['id'],
        amount=amount_paise,
        currency=settings.RAZORPAY_CURRENCY,
        status=PaymentRecord.STATUS_PENDING,
        metadata={'plan': plan_name, 'billing_cycle': billing_cycle},
        raw_response=rz_order,
    )

    logger.info(
        "Razorpay order created: order=%s user=%s plan=%s cycle=%s amount=%s",
        rz_order['id'], user.id, plan_name, billing_cycle, amount_paise,
    )

    return {
        'order_id': rz_order['id'],
        'amount': amount_paise,
        'currency': settings.RAZORPAY_CURRENCY,
        'key': settings.RAZORPAY_KEY_ID,
        'receipt': receipt,
        'plan': {
            'name': plan.name,
            'display_name': plan.display_name,
            'billing_cycle': billing_cycle,
        },
        'payment_record_id': record.id,
    }


def create_credit_pack_order(user, pack_id: str) -> dict:
    """Create a Razorpay order for a fixed prepaid credit pack.

    Credit pack prices are server-owned. The frontend only sends the pack ID.
    The project currently stores credits client-side, so this records the paid
    order but does not mutate a credit balance table.
    """
    pack = CREDIT_PACKS.get(pack_id)
    if not pack:
        raise ValueError("Invalid credit pack.")

    amount_paise = int(pack['amount_paise'])
    if amount_paise < 100:
        raise ValueError("Minimum Razorpay order amount is 100 paise.")

    client = _razorpay_client()
    receipt = f"cr_{user.id}_{pack_id}_{int(timezone.now().timestamp())}"
    rz_order = client.order.create({
        'amount': amount_paise,
        'currency': settings.RAZORPAY_CURRENCY,
        'receipt': receipt,
        'notes': {
            'user_id': str(user.id),
            'username': user.username,
            'credit_pack': pack_id,
            'credits': str(pack['credits']),
        },
    })

    sub = get_or_create_subscription(user)
    record = PaymentRecord.objects.create(
        user=user,
        subscription=sub,
        provider=PaymentRecord.PROVIDER_RAZORPAY,
        order_id=rz_order['id'],
        amount=amount_paise,
        currency=settings.RAZORPAY_CURRENCY,
        status=PaymentRecord.STATUS_PENDING,
        metadata={
            'type': 'credit_pack',
            'credit_pack': pack_id,
            'credits': pack['credits'],
            'pack_name': pack['name'],
        },
        raw_response=rz_order,
    )

    logger.info(
        "Razorpay credit order created: order=%s user=%s pack=%s amount=%s",
        rz_order['id'], user.id, pack_id, amount_paise,
    )

    return {
        'order_id': rz_order['id'],
        'amount': amount_paise,
        'currency': settings.RAZORPAY_CURRENCY,
        'key': settings.RAZORPAY_KEY_ID,
        'receipt': receipt,
        'credit_pack': {
            'id': pack_id,
            'name': pack['name'],
            'credits': pack['credits'],
        },
        'payment_record_id': record.id,
    }


# ---------------------------------------------------------------------------
# Payment verification  (called after Razorpay checkout success)
# ---------------------------------------------------------------------------

def verify_payment(user, order_id: str, payment_id: str, signature: str) -> PaymentRecord:
    """Verify the Razorpay payment signature server-side and activate subscription.

    Steps:
      1. Verify HMAC-SHA256 signature — abort immediately on mismatch.
      2. select_for_update() to prevent concurrent double-processing.
      3. Idempotency: if already paid, return the existing record.
      4. Mark PaymentRecord as paid.
      5. Activate / upgrade the UserSubscription.
    """
    _verify_payment_signature(order_id, payment_id, signature)

    with transaction.atomic():
        try:
            record = (
                PaymentRecord.objects
                .select_for_update()
                .get(order_id=order_id, user=user)
            )
        except PaymentRecord.DoesNotExist:
            logger.warning(
                "verify_payment: order %s not found for user %s", order_id, user.id
            )
            raise ValueError("Payment record not found.")

        if record.status == PaymentRecord.STATUS_PAID:
            logger.info("verify_payment: order %s already processed (idempotent)", order_id)
            return record

        record.payment_id = payment_id
        record.signature = signature
        record.status = PaymentRecord.STATUS_PAID
        record.paid_at = timezone.now()
        record.save(
            update_fields=['payment_id', 'signature', 'status', 'paid_at', 'updated_at']
        )

        plan_name = record.metadata.get('plan')
        billing_cycle = record.metadata.get('billing_cycle', 'monthly')
        if plan_name:
            _activate_subscription(user, record, plan_name, billing_cycle)

    logger.info(
        "Payment verified + subscription activated: user=%s order=%s payment=%s",
        user.id, order_id, payment_id,
    )
    return record


def _verify_payment_signature(order_id: str, payment_id: str, signature: str):
    """Raise ValueError if the Razorpay payment signature does not match."""
    expected = _hmac_sha256(settings.RAZORPAY_KEY_SECRET, f"{order_id}|{payment_id}")
    if not hmac.compare_digest(expected, signature):
        logger.warning(
            "Payment signature mismatch: order=%s payment=%s", order_id, payment_id
        )
        raise ValueError("Payment signature verification failed.")


# ---------------------------------------------------------------------------
# Subscription activation
# ---------------------------------------------------------------------------

def _activate_subscription(user, payment_record: PaymentRecord, plan_name: str, billing_cycle: str):
    """Upgrade UserSubscription and set expiry. Called inside an atomic block."""
    sub = upgrade_subscription(user, plan_name, billing_cycle)

    now = timezone.now()
    sub.ends_at = now + (timedelta(days=365) if billing_cycle == 'yearly' else timedelta(days=30))
    sub.provider = 'razorpay'
    sub.external_subscription_id = payment_record.order_id
    sub.auto_renew = True
    sub.save(
        update_fields=['ends_at', 'provider', 'external_subscription_id', 'auto_renew', 'updated_at']
    )

    payment_record.subscription = sub
    payment_record.save(update_fields=['subscription'])

    logger.info(
        "Subscription activated: user=%s plan=%s cycle=%s ends_at=%s",
        user.id, plan_name, billing_cycle, sub.ends_at,
    )
    return sub


# ---------------------------------------------------------------------------
# Webhook helpers
# ---------------------------------------------------------------------------

def verify_razorpay_webhook_signature(raw_body: bytes, received_signature: str) -> bool:
    """Verify an incoming Razorpay webhook using the webhook secret (not API secret)."""
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)


def store_webhook_event(
    provider: str, event_id: str, event_type: str, payload: dict
) -> tuple:
    """Persist a WebhookEvent. Returns (event, created).

    If event_id already exists (duplicate delivery), returns (existing_event, False)
    so the caller can ack without reprocessing.
    """
    try:
        event, created = WebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                'provider': provider,
                'event_type': event_type,
                'payload': payload,
            },
        )
        return event, created
    except IntegrityError:
        # Race between two simultaneous deliveries of the same event.
        event = WebhookEvent.objects.get(event_id=event_id)
        return event, False


def process_webhook_event(webhook_event_id: int):
    """Dispatch a stored WebhookEvent. Idempotent — called by Celery task."""
    try:
        event = WebhookEvent.objects.get(pk=webhook_event_id, processed=False)
    except WebhookEvent.DoesNotExist:
        return  # already processed or not found

    error = ''
    try:
        _dispatch_webhook(event)
    except Exception as exc:
        error = str(exc)[:500]
        logger.exception(
            "Webhook dispatch failed: event_id=%s type=%s", event.event_id, event.event_type
        )
        raise
    finally:
        WebhookEvent.objects.filter(pk=webhook_event_id).update(
            processed=(not error),
            processed_at=timezone.now() if not error else None,
            error=error,
        )


# ---------------------------------------------------------------------------
# Webhook event dispatch
# ---------------------------------------------------------------------------

def _dispatch_webhook(event: WebhookEvent):
    dispatch = {
        'payment.captured': _handle_payment_captured,
        'payment.failed': _handle_payment_failed,
        'subscription.charged': _handle_subscription_charged,
        'subscription.activated': _handle_subscription_charged,
        'subscription.cancelled': _handle_subscription_cancelled,
        'refund.processed': _handle_refund_processed,
    }
    handler = dispatch.get(event.event_type)
    if handler:
        handler(event.payload)
    else:
        logger.debug("Unhandled webhook event type: %s", event.event_type)


def _handle_payment_captured(payload: dict):
    """Server-side confirmation that a payment was captured.

    This is the authoritative source of truth — even if verify_payment was
    never called (e.g., the user closed the browser), we still activate.
    """
    entity = _extract_entity(payload, 'payment')
    payment_id = entity.get('id', '')
    order_id = entity.get('order_id', '')

    if not payment_id or not order_id:
        return

    with transaction.atomic():
        try:
            record = (
                PaymentRecord.objects
                .select_for_update()
                .get(order_id=order_id)
            )
        except PaymentRecord.DoesNotExist:
            logger.warning("payment.captured: no record for order %s", order_id)
            return

        if record.status == PaymentRecord.STATUS_PAID:
            return

        record.payment_id = payment_id
        record.status = PaymentRecord.STATUS_PAID
        record.paid_at = timezone.now()
        record.payment_method = entity.get('method', '')
        record.raw_response = entity
        record.save(
            update_fields=[
                'payment_id', 'status', 'paid_at',
                'payment_method', 'raw_response', 'updated_at',
            ]
        )

        plan_name = record.metadata.get('plan')
        billing_cycle = record.metadata.get('billing_cycle', 'monthly')
        if plan_name:
            _activate_subscription(record.user, record, plan_name, billing_cycle)

    logger.info("payment.captured processed: order=%s payment=%s", order_id, payment_id)


def _handle_payment_failed(payload: dict):
    entity = _extract_entity(payload, 'payment')
    order_id = entity.get('order_id', '')
    payment_id = entity.get('id', '')

    if not order_id:
        return

    updated = PaymentRecord.objects.filter(
        order_id=order_id,
        status=PaymentRecord.STATUS_PENDING,
    ).update(
        status=PaymentRecord.STATUS_FAILED,
        payment_id=payment_id,
    )
    if updated:
        logger.info("payment.failed processed: order=%s", order_id)


def _handle_subscription_charged(payload: dict):
    """Razorpay recurring subscription charge — extend ends_at."""
    sub_entity = _extract_entity(payload, 'subscription')
    external_id = sub_entity.get('id', '')

    if not external_id:
        return

    from plans.models import UserSubscription
    with transaction.atomic():
        try:
            sub = (
                UserSubscription.objects
                .select_for_update()
                .get(external_subscription_id=external_id)
            )
        except UserSubscription.DoesNotExist:
            return

        extension = timedelta(days=365 if sub.billing_cycle == 'yearly' else 30)
        now = timezone.now()
        sub.ends_at = max(sub.ends_at or now, now) + extension
        sub.status = 'active'
        sub.save(update_fields=['ends_at', 'status', 'updated_at'])

    logger.info("subscription.charged: extended ends_at for external_id=%s", external_id)


def _handle_subscription_cancelled(payload: dict):
    sub_entity = _extract_entity(payload, 'subscription')
    external_id = sub_entity.get('id', '')

    if not external_id:
        return

    from plans.models import UserSubscription
    updated = UserSubscription.objects.filter(
        external_subscription_id=external_id
    ).update(
        status='cancelled',
        cancelled_at=timezone.now(),
        auto_renew=False,
    )
    if updated:
        logger.info("subscription.cancelled: external_id=%s", external_id)


def _handle_refund_processed(payload: dict):
    entity = _extract_entity(payload, 'refund')
    payment_id = entity.get('payment_id', '')

    if not payment_id:
        return

    updated = PaymentRecord.objects.filter(payment_id=payment_id).update(
        status=PaymentRecord.STATUS_REFUNDED
    )
    if updated:
        logger.info("refund.processed: payment_id=%s", payment_id)


def _extract_entity(payload: dict, entity_key: str) -> dict:
    """Safely extract an entity from a Razorpay webhook payload."""
    try:
        return payload['payload'][entity_key]['entity']
    except (KeyError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_payment_history(user, limit: int = 20):
    """Return recent paid/failed/refunded records for a user."""
    return (
        PaymentRecord.objects
        .filter(user=user)
        .exclude(status=PaymentRecord.STATUS_PENDING)
        .order_by('-created_at')[:limit]
    )
