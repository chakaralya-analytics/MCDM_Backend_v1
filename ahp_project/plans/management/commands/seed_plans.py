"""
seed_plans — idempotent command that creates (or updates) the three canonical
subscription plans.  Safe to run multiple times.

Usage:
    python manage.py seed_plans
"""

from django.core.management.base import BaseCommand
from plans.models import SubscriptionPlan

PLANS = [
    {
        'name': SubscriptionPlan.PLAN_FREE,
        'display_name': 'Free',
        'description': 'Get started with AHP/TOPSIS analysis at no cost.',
        'monthly_price': '0.00',
        'yearly_price': '0.00',
        'max_projects': None,
        'max_alternatives_per_project': None,
        'max_criteria': None,
        'max_experts': None,
        'feature_flags': {
            'csv_export': False,
            'advanced_analytics': False,
            'ai_insights': False,
            'team_collaboration': False,
            'priority_support': False,
        },
        'is_active': True,
        'sort_order': 0,
    },
    {
        'name': SubscriptionPlan.PLAN_PRO,
        'display_name': 'Pro',
        'description': 'For professionals who need more projects, exports, and analytics.',
        'monthly_price': '999.00',
        'yearly_price': '9999.00',
        'max_projects': None,
        'max_alternatives_per_project': None,
        'max_criteria': None,
        'max_experts': None,
        'feature_flags': {
            'csv_export': True,
            'advanced_analytics': True,
            'ai_insights': False,
            'team_collaboration': False,
            'priority_support': False,
        },
        'is_active': True,
        'sort_order': 1,
    },
    {
        'name': SubscriptionPlan.PLAN_ENTERPRISE,
        'display_name': 'Enterprise',
        'description': 'Unlimited usage, team collaboration, AI insights, and priority support.',
        'monthly_price': '4999.00',
        'yearly_price': '49999.00',
        'max_projects': None,          # unlimited
        'max_alternatives_per_project': None,
        'max_criteria': None,
        'max_experts': None,
        'feature_flags': {
            'csv_export': True,
            'advanced_analytics': True,
            'ai_insights': True,
            'team_collaboration': True,
            'priority_support': True,
        },
        'is_active': True,
        'sort_order': 2,
    },
]


class Command(BaseCommand):
    help = 'Seed the three canonical subscription plans (idempotent).'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for data in PLANS:
            name = data.pop('name')
            obj, created = SubscriptionPlan.objects.update_or_create(
                name=name,
                defaults=data,
            )
            data['name'] = name  # restore for next run safety

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created plan: {obj.display_name}'))
            else:
                updated_count += 1
                self.stdout.write(f'  Updated plan: {obj.display_name}')

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. {created_count} created, {updated_count} updated.'
            )
        )
