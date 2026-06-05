# billing/models.py

from django.contrib.auth.models import User
from django.db import models


class PaymentRecord(models.Model):
    """Immutable audit trail of every payment attempt.

    amount is stored in the smallest currency unit (paise for INR).
    Idempotency is enforced via order_id uniqueness per user + select_for_update().
    Raw provider responses are kept verbatim for dispute resolution.
    """

    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    PROVIDER_RAZORPAY = 'razorpay'
    PROVIDER_STRIPE = 'stripe'
    PROVIDER_CHOICES = [
        (PROVIDER_RAZORPAY, 'Razorpay'),
        (PROVIDER_STRIPE, 'Stripe'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='payment_records'
    )
    subscription = models.ForeignKey(
        'plans.UserSubscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_records',
    )

    provider = models.CharField(
        max_length=20, choices=PROVIDER_CHOICES, default=PROVIDER_RAZORPAY
    )
    payment_id = models.CharField(max_length=255, blank=True, db_index=True)
    order_id = models.CharField(max_length=255, db_index=True)
    signature = models.CharField(max_length=500, blank=True)

    amount = models.PositiveIntegerField(
        help_text='Amount in smallest currency unit (paise for INR)'
    )
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    payment_method = models.CharField(max_length=100, blank=True)

    # Stores plan name and billing_cycle — never trust frontend for these.
    metadata = models.JSONField(default=dict, blank=True)
    # Full provider response for audit/dispute purposes.
    raw_response = models.JSONField(default=dict, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_paymentrecord'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='pay_user_status_idx'),
            models.Index(fields=['order_id'], name='pay_order_idx'),
            models.Index(fields=['payment_id'], name='pay_payment_idx'),
            models.Index(fields=['created_at'], name='pay_created_idx'),
        ]

    def __str__(self):
        rupees = self.amount / 100
        return f"{self.user.username} — ₹{rupees:.2f} ({self.status})"

    @property
    def amount_rupees(self):
        return self.amount / 100


class WebhookEvent(models.Model):
    """Idempotency log for incoming provider webhook events.

    event_id is unique — duplicate deliveries are silently acknowledged
    by returning 200 without reprocessing.

    payload stores the full raw event body for auditability and manual replay.
    """

    PROVIDER_RAZORPAY = 'razorpay'
    PROVIDER_CHOICES = [(PROVIDER_RAZORPAY, 'Razorpay')]

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_webhookevent'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'event_type'], name='webhook_prov_type_idx'),
            models.Index(fields=['processed', 'created_at'], name='webhook_proc_created_idx'),
        ]

    def __str__(self):
        mark = '✓' if self.processed else '⏳'
        return f"{self.event_type} {mark} [{self.event_id[:20]}]"
