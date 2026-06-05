# billing/migrations/0001_initial.py

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('plans', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebhookEvent',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                )),
                ('provider', models.CharField(
                    choices=[('razorpay', 'Razorpay')], max_length=20
                )),
                ('event_id', models.CharField(db_index=True, max_length=255, unique=True)),
                ('event_type', models.CharField(db_index=True, max_length=100)),
                ('payload', models.JSONField(default=dict)),
                ('processed', models.BooleanField(db_index=True, default=False)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'billing_webhookevent',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(
                        fields=['provider', 'event_type'], name='webhook_prov_type_idx'
                    ),
                    models.Index(
                        fields=['processed', 'created_at'], name='webhook_proc_created_idx'
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name='PaymentRecord',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                )),
                ('provider', models.CharField(
                    choices=[('razorpay', 'Razorpay'), ('stripe', 'Stripe')],
                    default='razorpay', max_length=20,
                )),
                ('payment_id', models.CharField(blank=True, db_index=True, max_length=255)),
                ('order_id', models.CharField(db_index=True, max_length=255)),
                ('signature', models.CharField(blank=True, max_length=500)),
                ('amount', models.PositiveIntegerField(
                    help_text='Amount in smallest currency unit (paise for INR)'
                )),
                ('currency', models.CharField(default='INR', max_length=10)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('paid', 'Paid'),
                        ('failed', 'Failed'),
                        ('refunded', 'Refunded'),
                    ],
                    default='pending', max_length=20,
                )),
                ('payment_method', models.CharField(blank=True, max_length=100)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('raw_response', models.JSONField(blank=True, default=dict)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='payment_records',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('subscription', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payment_records',
                    to='plans.usersubscription',
                )),
            ],
            options={
                'db_table': 'billing_paymentrecord',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'status'], name='pay_user_status_idx'),
                    models.Index(fields=['order_id'], name='pay_order_idx'),
                    models.Index(fields=['payment_id'], name='pay_payment_idx'),
                    models.Index(fields=['created_at'], name='pay_created_idx'),
                ],
            },
        ),
    ]
