# billing/admin.py

from django.contrib import admin
from django.utils.html import format_html

from .models import PaymentRecord, WebhookEvent


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'status_badge', 'amount_display', 'currency',
        'payment_method', 'provider', 'paid_at', 'created_at',
    ]
    list_filter = ['status', 'provider', 'currency', 'payment_method']
    search_fields = [
        'user__username', 'user__email',
        'payment_id', 'order_id',
    ]
    raw_id_fields = ['user', 'subscription']
    readonly_fields = [
        'created_at', 'updated_at', 'raw_response',
        'amount_display', 'status_badge', 'metadata',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = [
        ('User & Plan', {
            'fields': ['user', 'subscription', 'metadata'],
        }),
        ('Payment Details', {
            'fields': [
                'provider', 'order_id', 'payment_id', 'signature',
                'amount_display', 'currency', 'payment_method',
                'status', 'paid_at',
            ],
        }),
        ('Audit', {
            'classes': ['collapse'],
            'fields': ['raw_response', 'created_at', 'updated_at'],
        }),
    ]

    @admin.display(description='Amount')
    def amount_display(self, obj):
        return f'₹{obj.amount_rupees:.2f}'

    @admin.display(description='Status')
    def status_badge(self, obj):
        colours = {
            'paid': '#16a34a',
            'pending': '#d97706',
            'failed': '#dc2626',
            'refunded': '#6b7280',
        }
        colour = colours.get(obj.status, '#374151')
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colour, obj.get_status_display(),
        )


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        'event_type', 'provider', 'event_id_short',
        'processed_badge', 'processed_at', 'created_at',
    ]
    list_filter = ['processed', 'provider', 'event_type']
    search_fields = ['event_id', 'event_type']
    readonly_fields = ['created_at', 'processed_at', 'payload', 'event_id']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = [
        ('Event', {
            'fields': ['provider', 'event_id', 'event_type'],
        }),
        ('Processing', {
            'fields': ['processed', 'processed_at', 'error'],
        }),
        ('Payload', {
            'classes': ['collapse'],
            'fields': ['payload'],
        }),
        ('Timestamps', {
            'classes': ['collapse'],
            'fields': ['created_at'],
        }),
    ]

    @admin.display(description='Event ID')
    def event_id_short(self, obj):
        return obj.event_id[:32] + ('…' if len(obj.event_id) > 32 else '')

    @admin.display(description='Processed', boolean=True)
    def processed_badge(self, obj):
        return obj.processed
