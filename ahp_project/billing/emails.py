"""
billing/emails.py — Transactional email helpers for billing events.

All sends go through _send(), which catches and logs failures so a broken
email backend never propagates an exception into the calling request or task.

Switch delivery provider by changing EMAIL_BACKEND in settings.py:
  - django.core.mail.backends.console.EmailBackend  (local dev)
  - django.core.mail.backends.smtp.EmailBackend     (SMTP / Gmail / SES relay)
  - anymail backends                                (SendGrid, Mailgun, Postmark…)
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

_APP = getattr(settings, 'APP_NAME', 'MCDM Platform')
_URL = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')


# ---------------------------------------------------------------------------
# Public helpers — called from tasks.py
# ---------------------------------------------------------------------------

def send_welcome_email(user_email: str, username: str) -> None:
    _send(
        subject=f'Welcome to {_APP}!',
        message=(
            f'Hi {username},\n\n'
            f'Thanks for signing up. Your free account is ready.\n\n'
            f'Get started: {_URL}/dashboard\n\n'
            f'— The {_APP} team'
        ),
        recipient=user_email,
        tag='welcome',
    )


def send_payment_receipt(
    user_email: str,
    username: str,
    plan_display: str,
    amount_rupees: str,
    payment_id: str,
) -> None:
    _send(
        subject=f'{_APP} — Payment confirmed',
        message=(
            f'Hi {username},\n\n'
            f'Your payment was successful.\n\n'
            f'  Plan:       {plan_display}\n'
            f'  Amount:     ₹{amount_rupees}\n'
            f'  Payment ID: {payment_id}\n\n'
            f'Manage your subscription: {_URL}/billing/usage\n\n'
            f'— The {_APP} team'
        ),
        recipient=user_email,
        tag='payment_receipt',
    )


def send_upgrade_confirmation(
    user_email: str,
    username: str,
    plan_display: str,
    ends_at_str: str,
) -> None:
    _send(
        subject=f'{_APP} — Subscription upgraded to {plan_display}',
        message=(
            f'Hi {username},\n\n'
            f'Your account has been upgraded to the {plan_display} plan.\n'
            f'Active until: {ends_at_str}\n\n'
            f'— The {_APP} team'
        ),
        recipient=user_email,
        tag='upgrade_confirmation',
    )


def send_expiry_warning(user_email: str, username: str, days_remaining: int) -> None:
    day_word = 'day' if days_remaining == 1 else 'days'
    _send(
        subject=f'{_APP} — Your subscription expires in {days_remaining} {day_word}',
        message=(
            f'Hi {username},\n\n'
            f'Your subscription expires in {days_remaining} {day_word}.\n'
            f'Renew at {_URL}/billing/plans to keep uninterrupted access.\n\n'
            f'— The {_APP} team'
        ),
        recipient=user_email,
        tag='expiry_warning',
    )


def send_payment_failure_notice(
    user_email: str,
    username: str,
    order_id: str,
) -> None:
    _send(
        subject=f'{_APP} — Payment could not be processed',
        message=(
            f'Hi {username},\n\n'
            f'We were unable to process your payment (order {order_id}).\n'
            f'Please try again: {_URL}/billing/plans\n\n'
            f'If you continue to experience issues, contact support.\n\n'
            f'— The {_APP} team'
        ),
        recipient=user_email,
        tag='payment_failure',
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _send(subject: str, message: str, recipient: str, tag: str = '') -> None:
    """Send a plain-text email, logging success and swallowing delivery errors."""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_FROM,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info('Email sent: tag=%s to=%s', tag, recipient)
    except Exception:
        logger.exception('Email send failed: tag=%s to=%s', tag, recipient)
