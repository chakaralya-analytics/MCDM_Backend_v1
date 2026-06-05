# billing/tasks.py

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    name='billing.process_webhook_event',
    acks_late=True,
)
def process_webhook_event_task(self, webhook_event_id: int):
    """Asynchronously process a stored WebhookEvent.

    Retries up to 5× with 60s delay. acks_late=True prevents task loss if
    the worker crashes mid-flight.
    """
    try:
        from .services.billing_service import process_webhook_event
        process_webhook_event(webhook_event_id)
    except Exception as exc:
        logger.exception(
            'Webhook task failed (attempt %d/%d): event_id=%s',
            self.request.retries + 1,
            self.max_retries + 1,
            webhook_event_id,
        )
        raise self.retry(exc=exc)


@shared_task(name='billing.send_welcome_email', max_retries=3, default_retry_delay=30)
def send_welcome_email_task(user_id: int):
    """Send a welcome email to a newly registered user."""
    from django.contrib.auth.models import User
    from .emails import send_welcome_email
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    send_welcome_email(user.email, user.username)


@shared_task(name='billing.send_payment_success_email', max_retries=3, default_retry_delay=30)
def send_payment_success_email(user_id: int, payment_record_id: int):
    """Send payment confirmation email with receipt details."""
    from django.contrib.auth.models import User
    from .models import PaymentRecord
    from .emails import send_payment_receipt
    try:
        user = User.objects.get(pk=user_id)
        record = PaymentRecord.objects.get(pk=payment_record_id)
    except (User.DoesNotExist, PaymentRecord.DoesNotExist):
        return

    plan_name = (record.metadata or {}).get('plan_name', 'Pro')
    amount_rupees = f'{record.amount / 100:.2f}'
    send_payment_receipt(user.email, user.username, plan_name, amount_rupees, record.payment_id or '')


@shared_task(name='billing.send_payment_failure_notification', max_retries=3, default_retry_delay=30)
def send_payment_failure_notification(user_id: int, order_id: str):
    """Notify user of a failed payment attempt."""
    from django.contrib.auth.models import User
    from .emails import send_payment_failure_notice
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    send_payment_failure_notice(user.email, user.username, order_id)


@shared_task(name='billing.send_subscription_expiry_reminder', max_retries=3, default_retry_delay=60)
def send_subscription_expiry_reminder(user_id: int, days_remaining: int):
    """Remind user their subscription is expiring soon."""
    from django.contrib.auth.models import User
    from .emails import send_expiry_warning
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    send_expiry_warning(user.email, user.username, days_remaining)


@shared_task(name='billing.check_expiring_subscriptions', max_retries=1)
def check_expiring_subscriptions():
    """Periodic task: find subscriptions expiring in ≤7 days and enqueue reminders.

    Schedule via Celery Beat:
        'check-expiring-subscriptions': {
            'task': 'billing.check_expiring_subscriptions',
            'schedule': crontab(hour=9, minute=0),
        }
    """
    from datetime import timedelta
    from django.utils import timezone
    from plans.models import UserSubscription

    now = timezone.now()
    threshold = now + timedelta(days=7)
    expiring = UserSubscription.objects.filter(
        status='active',
        ends_at__isnull=False,
        ends_at__lte=threshold,
        ends_at__gt=now,
    ).select_related('user')

    count = 0
    for sub in expiring:
        days = (sub.ends_at - now).days
        send_subscription_expiry_reminder.delay(sub.user_id, days)
        count += 1

    logger.info('check_expiring_subscriptions: enqueued %d reminders', count)
