# plans/migrations/0001_initial.py

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    choices=[('free', 'Free'), ('pro', 'Pro'), ('enterprise', 'Enterprise')],
                    max_length=50,
                    unique=True,
                )),
                ('display_name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('monthly_price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('yearly_price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('max_projects', models.IntegerField(blank=True, null=True)),
                ('max_alternatives_per_project', models.IntegerField(blank=True, null=True)),
                ('max_criteria', models.IntegerField(blank=True, null=True)),
                ('max_experts', models.IntegerField(blank=True, null=True)),
                ('feature_flags', models.JSONField(default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.IntegerField(default=0, help_text='Lower value = shown first')),
                ('razorpay_plan_id_monthly', models.CharField(blank=True, max_length=200)),
                ('razorpay_plan_id_yearly', models.CharField(blank=True, max_length=200)),
                ('stripe_price_id_monthly', models.CharField(blank=True, max_length=200)),
                ('stripe_price_id_yearly', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'plans_subscriptionplan',
                'ordering': ['sort_order', 'monthly_price'],
                'indexes': [
                    models.Index(fields=['name'], name='plan_name_idx'),
                    models.Index(fields=['is_active'], name='plan_active_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='UserSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('trialing', 'Trialing'),
                        ('active', 'Active'),
                        ('cancelled', 'Cancelled'),
                        ('expired', 'Expired'),
                        ('past_due', 'Past Due'),
                    ],
                    default='active',
                    max_length=20,
                )),
                ('billing_cycle', models.CharField(
                    choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')],
                    default='monthly',
                    max_length=10,
                )),
                ('starts_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('ends_at', models.DateTimeField(blank=True, help_text='null = no expiry (Free)', null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('trial_ends_at', models.DateTimeField(blank=True, null=True)),
                ('auto_renew', models.BooleanField(default=True)),
                ('external_subscription_id', models.CharField(blank=True, max_length=200)),
                ('provider', models.CharField(
                    choices=[
                        ('internal', 'Internal'),
                        ('razorpay', 'Razorpay'),
                        ('stripe', 'Stripe'),
                    ],
                    default='internal',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subscription',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='subscriptions',
                    to='plans.subscriptionplan',
                )),
            ],
            options={
                'db_table': 'plans_usersubscription',
                'indexes': [
                    models.Index(fields=['user'], name='sub_user_idx'),
                    models.Index(fields=['status'], name='sub_status_idx'),
                    models.Index(fields=['ends_at'], name='sub_ends_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='UsageTracking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField()),
                ('month', models.IntegerField()),
                ('projects_created', models.IntegerField(default=0)),
                ('alternatives_created', models.IntegerField(default=0)),
                ('calculations_run', models.IntegerField(default=0)),
                ('api_calls', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usage_records',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'plans_usagetracking',
                'unique_together': {('user', 'year', 'month')},
                'indexes': [
                    models.Index(fields=['user', 'year', 'month'], name='usage_user_period_idx'),
                ],
            },
        ),
    ]
