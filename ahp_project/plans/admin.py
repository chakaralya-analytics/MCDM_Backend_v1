# plans/admin.py

from django.contrib import admin
from .models import SubscriptionPlan, UserSubscription, UsageTracking


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'monthly_price', 'yearly_price',
                    'max_projects', 'max_alternatives_per_project', 'is_active', 'sort_order']
    list_filter = ['is_active', 'name']
    search_fields = ['name', 'display_name']
    ordering = ['sort_order', 'monthly_price']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'billing_cycle', 'is_active', 'starts_at', 'ends_at']
    list_filter = ['status', 'billing_cycle', 'provider', 'plan']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']

    @admin.display(boolean=True, description='Active?')
    def is_active(self, obj):
        return obj.is_active


@admin.register(UsageTracking)
class UsageTrackingAdmin(admin.ModelAdmin):
    list_display = ['user', 'year', 'month', 'projects_created',
                    'alternatives_created', 'calculations_run', 'api_calls']
    list_filter = ['year', 'month']
    search_fields = ['user__username']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']
