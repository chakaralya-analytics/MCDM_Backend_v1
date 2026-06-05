"""
usage_service.py — thin helpers for incrementing and querying UsageTracking.

UsageTracking rows are for reporting only.  Quota enforcement always uses
live ORM counts in subscription_service.  Never gate access on these counters.
"""

import logging
from ..models import UsageTracking

logger = logging.getLogger(__name__)

# Map caller-facing event names to UsageTracking field names.
_EVENT_FIELD = {
    'project_created': 'projects_created',
    'alternative_created': 'alternatives_created',
    'calculation_run': 'calculations_run',
    'api_call': 'api_calls',
}


def track_event(user, event, amount=1):
    """Increment the usage counter for *event* (see _EVENT_FIELD map).

    Silently ignores unknown events rather than crashing a request — usage
    tracking is non-critical reporting, not quota enforcement.
    """
    field = _EVENT_FIELD.get(event)
    if not field:
        logger.warning("track_event: unknown event %r for user id=%s", event, user.id)
        return

    record = UsageTracking.get_or_create_current(user)
    record.increment(field, amount)
    logger.debug("Usage tracked: user=%s event=%s field=%s amount=%s", user.id, event, field, amount)


def get_current_usage(user):
    """Return the current-month UsageTracking row as a dict, or zeros if none."""
    record = UsageTracking.get_or_create_current(user)
    return {
        'projects_created': record.projects_created,
        'alternatives_created': record.alternatives_created,
        'calculations_run': record.calculations_run,
        'api_calls': record.api_calls,
        'period': f"{record.year}-{record.month:02d}",
    }
