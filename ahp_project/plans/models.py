# plans/models.py

from django.contrib.auth.models import User
from django.db import models
from django.db.models import F
from django.utils import timezone


class SubscriptionPlan(models.Model):
    """Defines a tier of service with specific feature flags and usage limits.

    null on a limit field means *unlimited* (Enterprise).
    Payment provider IDs are left blank until Phase 4 (Razorpay / Stripe).
    """

    PLAN_FREE = 'free'
    PLAN_PRO = 'pro'
    PLAN_ENTERPRISE = 'enterprise'
    PLAN_CHOICES = [
        (PLAN_FREE, 'Free'),
        (PLAN_PRO, 'Pro'),
        (PLAN_ENTERPRISE, 'Enterprise'),
    ]

    name = models.CharField(max_length=50, unique=True, choices=PLAN_CHOICES)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # null = unlimited (Enterprise tier)
    max_projects = models.IntegerField(null=True, blank=True)
    max_alternatives_per_project = models.IntegerField(null=True, blank=True)
    max_criteria = models.IntegerField(null=True, blank=True)
    max_experts = models.IntegerField(null=True, blank=True)

    # Dict of feature_name → bool.
    # Keys: csv_export, advanced_analytics, ai_insights, team_collaboration, priority_support
    feature_flags = models.JSONField(default=dict)

    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0, help_text='Lower value = shown first')

    # Phase 4 (Razorpay / Stripe) — populated when payment integration lands.
    razorpay_plan_id_monthly = models.CharField(max_length=200, blank=True)
    razorpay_plan_id_yearly = models.CharField(max_length=200, blank=True)
    stripe_price_id_monthly = models.CharField(max_length=200, blank=True)
    stripe_price_id_yearly = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'plans_subscriptionplan'
        ordering = ['sort_order', 'monthly_price']
        indexes = [
            models.Index(fields=['name'], name='plan_name_idx'),
            models.Index(fields=['is_active'], name='plan_active_idx'),
        ]

    def __str__(self):
        return f"{self.display_name} (₹{self.monthly_price}/mo)"

    def has_feature(self, feature_name):
        return bool(self.feature_flags.get(feature_name, False))

    def get_limit(self, resource):
        """Return the numeric limit or None if unlimited."""
        return getattr(self, f'max_{resource}', None)


class UserSubscription(models.Model):
    """Tracks which plan a user is subscribed to and when.

    One subscription per user (OneToOne).  Status lifecycle:
        trialing → active → cancelled / expired / past_due

    external_subscription_id and provider are blank until Phase 4.
    """

    STATUS_TRIALING = 'trialing'
    STATUS_ACTIVE = 'active'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CHOICES = [
        (STATUS_TRIALING, 'Trialing'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_PAST_DUE, 'Past Due'),
    ]

    CYCLE_MONTHLY = 'monthly'
    CYCLE_YEARLY = 'yearly'
    BILLING_CYCLE_CHOICES = [
        (CYCLE_MONTHLY, 'Monthly'),
        (CYCLE_YEARLY, 'Yearly'),
    ]

    PROVIDER_INTERNAL = 'internal'
    PROVIDER_RAZORPAY = 'razorpay'
    PROVIDER_STRIPE = 'stripe'
    PROVIDER_CHOICES = [
        (PROVIDER_INTERNAL, 'Internal'),
        (PROVIDER_RAZORPAY, 'Razorpay'),
        (PROVIDER_STRIPE, 'Stripe'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default=CYCLE_MONTHLY)

    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True, help_text='null = no expiry (Free)')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)

    # Phase 4 — populated by payment webhook handlers.
    external_subscription_id = models.CharField(max_length=200, blank=True)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default=PROVIDER_INTERNAL)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'plans_usersubscription'
        indexes = [
            models.Index(fields=['user'], name='sub_user_idx'),
            models.Index(fields=['status'], name='sub_status_idx'),
            models.Index(fields=['ends_at'], name='sub_ends_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.plan.display_name} ({self.status})"

    @property
    def is_active(self):
        if self.status not in (self.STATUS_ACTIVE, self.STATUS_TRIALING):
            return False
        if self.ends_at and timezone.now() > self.ends_at:
            return False
        return True

    @property
    def is_trial(self):
        if self.status != self.STATUS_TRIALING:
            return False
        if self.trial_ends_at and timezone.now() > self.trial_ends_at:
            return False
        return True

    def has_feature(self, feature_name):
        return self.plan.has_feature(feature_name)

    def remaining_days(self):
        if not self.ends_at:
            return None
        delta = self.ends_at - timezone.now()
        return max(0, delta.days)

    def get_limit(self, resource):
        return self.plan.get_limit(resource)


class UsageTracking(models.Model):
    """Monthly activity counters per user.

    Purpose: reporting and admin visibility — NOT quota enforcement.
    Quota enforcement always uses live ORM counts (AHPProject.count(), etc.)
    so it can never be cheated by manipulating these rows.

    Increments are done via F() expressions to be race-condition safe.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='usage_records')
    year = models.IntegerField()
    month = models.IntegerField()

    projects_created = models.IntegerField(default=0)
    alternatives_created = models.IntegerField(default=0)
    calculations_run = models.IntegerField(default=0)
    api_calls = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'plans_usagetracking'
        unique_together = [('user', 'year', 'month')]
        indexes = [
            models.Index(fields=['user', 'year', 'month'], name='usage_user_period_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.year}/{self.month:02d}"

    @classmethod
    def get_or_create_current(cls, user):
        now = timezone.now()
        obj, _ = cls.objects.get_or_create(
            user=user,
            year=now.year,
            month=now.month,
        )
        return obj

    def increment(self, field, amount=1):
        UsageTracking.objects.filter(pk=self.pk).update(
            **{field: F(field) + amount}
        )
        setattr(self, field, getattr(self, field) + amount)
